#!/usr/bin/env python3
"""Exercise actual allocation failure in owned native probes, with lower limits."""
import os
from pathlib import Path
import resource
import threading
import time
import shutil
import subprocess
import sys
from native_limits import allocation_probe


def main():
    repo = Path(__file__).resolve().parents[1]
    root = repo / 'build/location-oom-fixture'
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(mode=0o700)
    initial = root / 'initial'; initial.mkdir()
    target = root / 'large'; target.mkdir()
    (initial / 'proof.txt').write_text('retained')
    # Split links among four inodes to stay below filesystem hardlink limits.
    seeds = [root / f'seed-{i}' for i in range(4)]
    for seed in seeds: seed.write_text('x')
    try:
        for i in range(100000):
            os.link(seeds[i // 25000], target / f'entry-{i:06}')
        # A legal 4095-byte directory can contain a child whose full path
        # exceeds the app representation. Create that child relative to dirfd.
        long_dir = root / 'long'; long_dir.mkdir()
        while len(os.fsencode(long_dir)) < 3850:
            long_dir = long_dir / ('d' * 200); long_dir.mkdir()
        fd = os.open(long_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            child = os.open('z' * 255, os.O_WRONLY | os.O_CREAT, 0o600, dir_fd=fd); os.close(child)
        finally: os.close(fd)
        for executable in sys.argv[1:]:
            result, cap = allocation_probe([executable, '--oom', str(initial), str(target)], initial / 'oom-ready')
            assert result.returncode == 0, f'{executable}: {result.returncode}: {result.stdout[-1500:]} {result.stderr[-1500:]}'
            assert 'Actual allocation failure preserved route/selection/history' in result.stdout
            print(f'{Path(executable).name}, RLIMIT_AS={cap}: {result.stdout.strip()}', flush=True)
            result = subprocess.run([executable, '--path-limit', str(initial), str(long_dir)], capture_output=True, text=True, timeout=30)
            assert result.returncode == 0 and 'Unrepresentable child path preserved' in result.stdout, result.stdout[-1500:]
            print(result.stdout.strip(), flush=True)
            # Synchronize on the native process before changing its own target
            # continuously during the large read. No product injection hooks.
            ready = initial / 'race-ready'
            ready.unlink(missing_ok=True)
            proc = subprocess.Popen([executable, '--race', str(initial), str(target)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stop = threading.Event()
            def mutate():
                left = target / 'mutating-a'; right = target / 'mutating-b'
                left.write_text('owned')
                while not stop.is_set():
                    os.rename(left, right); os.rename(right, left)
            thread = None
            try:
                deadline = time.monotonic() + 10
                while not ready.exists() and proc.poll() is None and time.monotonic() < deadline: time.sleep(.002)
                assert ready.exists() and proc.poll() is None, 'native race probe ready marker timeout'
                thread = threading.Thread(target=mutate); thread.start()
                output, error = proc.communicate(timeout=30)
                assert proc.returncode == 0 and b'Concurrent directory mutation preserved' in output, (proc.returncode, output[-1500:], error[-1500:])
                print(output.decode().strip(), flush=True)
            finally:
                stop.set()
                if thread: thread.join(timeout=5); assert not thread.is_alive()
                if proc.poll() is None: proc.terminate(); proc.wait(timeout=10)
                if proc.stdout: proc.stdout.close()
                if proc.stderr: proc.stderr.close()
    finally:
        shutil.rmtree(root)


if __name__ == '__main__':
    main()
