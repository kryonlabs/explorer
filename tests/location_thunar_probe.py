#!/usr/bin/env python3
"""Verify installed Thunar's location completion keys on a private desktop."""
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time


def main():
    assert os.environ.get('DISPLAY') and os.environ.get('XDG_RUNTIME_DIR')
    repo = Path(__file__).resolve().parents[1]
    root = repo / 'build/location-thunar-fixture'
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(mode=0o700)
    for name in ('alpha space', 'alpine'):
        (root / name).mkdir()
    (root / 'alps.txt').write_text('file')
    log = (root / 'thunar.log').open('wb')
    proc = subprocess.Popen(['thunar', str(root)], stdout=log, stderr=log)
    peer = None
    try:
        deadline = time.monotonic() + 15
        window = None
        while time.monotonic() < deadline:
            assert proc.poll() is None, 'owned Thunar exited'
            found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(proc.pid)], capture_output=True, text=True)
            if found.returncode == 0:
                window = found.stdout.splitlines()[0]; break
            time.sleep(.05)
        assert window, 'missing owned Thunar window'
        def xdo(*args):
            return subprocess.run(['xdotool', *map(str, args)], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
        def key(*items):
            for item in items:
                xdo('key', '--clearmodifiers', item); time.sleep(.25)
        def text():
            key('ctrl+a', 'ctrl+c')
            return subprocess.check_output([sys.executable, str(repo / 'tests/file_clipboard_test.py'), '--read', 'UTF8_STRING'], timeout=15).decode()
        xdo('windowfocus', '--sync', window); time.sleep(.5)
        payload = root / 'payload'; payload.write_text(str(root / 'al'))
        peer = subprocess.Popen([sys.executable, str(repo / 'tests/file_clipboard_test.py'), '--offer', 'UTF8_STRING', str(payload)], stdout=subprocess.PIPE, stderr=log)
        assert select.select([peer.stdout], [], [], 10)[0] and peer.stdout.readline().strip() == b'READY'
        key('ctrl+l', 'ctrl+a', 'ctrl+v', 'End', 'Tab')
        prefix = text(); print('Thunar Tab:', repr(prefix), flush=True)
        assert prefix == str(root / 'alp'), prefix
        # Copying the field dismisses GTK's popup. Reopen it before checking
        # keyboard selection, then inspect the accepted value after Return.
        key('End', 'Tab', 'Down', 'Return')
        first = text(); print('Thunar Tab/Down/Return:', repr(first), flush=True)
        assert first == str(root / 'alpha space') + '/', first
        key('Escape', 'Escape', 'ctrl+l')
        reset = text(); print('Thunar Escape:', repr(reset), flush=True)
        assert reset.rstrip('/') == str(root), reset
        print('Installed Thunar common-prefix/popup keys/Escape verified; Shelf file-parent selection follows current upstream, not4.20.2 file launch', flush=True)
    finally:
        if peer:
            if peer.poll() is None: peer.terminate()
            peer.wait(timeout=10); peer.stdout.close()
        if proc.poll() is None: proc.terminate()
        proc.wait(timeout=10); log.close()


if __name__ == '__main__':
    main()
