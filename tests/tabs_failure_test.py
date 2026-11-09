#!/usr/bin/env python3
"""Actual native heap exhaustion, confined to an owned private fixture."""
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import os
import threading
import time
from native_limits import allocation_probe

root = Path(__file__).resolve().parents[1] / 'build/tabs-failure-fixture'
shutil.rmtree(root, ignore_errors=True)
root.mkdir(mode=0o700)
(root / 'selected.txt').write_text('owned')
try:
    for executable in sys.argv[1:]:
        result, ceiling = allocation_probe([executable, '--oom', str(root)], root / 'oom-ready')
        assert result.returncode == 0, (result.returncode, result.stdout[-1200:], result.stderr[-1200:])
        assert 'Actual tab allocation failure retained' in result.stdout
        print(result.stdout.strip(), flush=True)
        for mode in ('--switch-oom', '--close-oom', '--switch-race', '--switch-denied'):
            initial = root / 'initial'; target = root / 'target'
            shutil.rmtree(initial, ignore_errors=True); shutil.rmtree(target, ignore_errors=True)
            initial.mkdir(); target.mkdir(); (initial / 'selected').write_text('owned')
            proc = subprocess.Popen([executable, mode, str(initial), str(target)],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            thread = None; stop = threading.Event()
            try:
                deadline = time.monotonic() + 15
                while not (initial / 'ready').exists() and proc.poll() is None and time.monotonic() < deadline: time.sleep(.005)
                assert (initial / 'ready').exists() and proc.poll() is None, 'native ready timeout'
                if mode == '--switch-denied': target.chmod(0)
                else:
                    for i in range(30000): (target / (f'{i:05d}-' + 'x' * 180)).touch()
                    if mode.endswith('oom'):
                        resource.prlimit(proc.pid, resource.RLIMIT_AS, (32 * 1024 * 1024,) * 2)
                    else:
                        left = target / 'mutating-a'; right = target / 'mutating-b'; left.write_text('owned')
                        def mutate():
                            while not stop.is_set(): os.rename(left, right); os.rename(right, left)
                        thread = threading.Thread(target=mutate); thread.start()
                output, error = proc.communicate(input=b'G', timeout=45)
                assert proc.returncode == 0 and b'Rejected tab' in output, (mode, proc.returncode, output[-1200:], error[-1200:])
                print(output.decode().strip(), flush=True)
            finally:
                stop.set()
                if thread: thread.join(timeout=5); assert not thread.is_alive()
                if proc.poll() is None: proc.terminate(); proc.wait(timeout=10)
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    if stream: stream.close()
                target.chmod(0o700)
finally:
    shutil.rmtree(root)
