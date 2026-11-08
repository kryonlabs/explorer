#!/usr/bin/env python3
"""Actual native secondary-pane allocation/read failures in owned fixtures."""
from pathlib import Path
import os
import resource
import shutil
import subprocess
import sys
import threading
import time

root = Path(__file__).resolve().parents[1] / 'build/split-failure-fixture'
root.mkdir(mode=0o700, exist_ok=True)
try:
    for executable in sys.argv[1:]:
        for mode in ('oom', 'missing', 'denied', 'race'):
            fixture = root / mode
            shutil.rmtree(fixture, ignore_errors=True)
            fixture.mkdir(mode=0o700)
            (fixture / 'selected').write_text('owned')
            proc = subprocess.Popen([sys.executable, 'tests/private_desktop.py', '--headless',
                                     executable, '--' + mode, str(fixture)],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stop = threading.Event(); thread = None; native_pid = None
            try:
                deadline = time.monotonic() + 20
                while not (fixture / 'ready').exists() and proc.poll() is None and time.monotonic() < deadline:
                    time.sleep(.005)
                assert (fixture / 'ready').exists() and proc.poll() is None, 'native ready timeout'
                # Find only this private wrapper's descendant with our exact executable.
                def descendants(parent):
                    children = Path(f'/proc/{parent}/task/{parent}/children').read_text().split()
                    for child in map(int, children):
                        yield child
                        yield from descendants(child)
                for child in (proc.pid, *descendants(proc.pid)):
                    try:
                        if Path(f'/proc/{child}/exe').resolve() == Path(executable).resolve(): native_pid = child
                    except FileNotFoundError: pass
                assert native_pid is not None, 'owned native PID missing'
                if mode == 'oom':
                    pages = int(Path(f'/proc/{native_pid}/statm').read_text().split()[0])
                    ceiling = pages * os.sysconf('SC_PAGE_SIZE')
                    resource.prlimit(native_pid, resource.RLIMIT_AS, (ceiling, ceiling))
                elif mode == 'missing':
                    shutil.rmtree(fixture)
                elif mode == 'denied':
                    fixture.chmod(0)
                else:
                    for i in range(12000): (fixture / (f'{i:05d}-' + 'x' * 180)).touch()
                    a, b = fixture / 'mutating-a', fixture / 'mutating-b'
                    a.write_text('owned')
                    def mutate():
                        while not stop.is_set(): os.rename(a, b); os.rename(b, a)
                    thread = threading.Thread(target=mutate); thread.start()
                output, error = proc.communicate(input=b'G', timeout=60)
                assert proc.returncode == 0 and b'Rejected secondary creation' in output, (
                    executable, mode, proc.returncode, output[-1600:], error[-1600:])
                if mode == 'denied': fixture.chmod(0o700)
                if mode != 'missing': assert (fixture / 'selected').read_text() == 'owned'
                print(output.decode().strip(), flush=True)
            finally:
                stop.set()
                if thread: thread.join(timeout=5); assert not thread.is_alive()
                if fixture.exists(): fixture.chmod(0o700)
                if proc.poll() is None: proc.terminate(); proc.wait(timeout=10)
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    if stream: stream.close()
finally:
    shutil.rmtree(root)
