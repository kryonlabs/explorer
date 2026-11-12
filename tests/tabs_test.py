#!/usr/bin/env python3
"""Owned native TabBar overflow, reorder and focus on a private desktop."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path, default=repo / 'build/explorer-desktop')
    parser.add_argument('--capture-prefix', default='tabs')
    args = parser.parse_args()
    assert os.environ.get('DISPLAY') and os.environ.get('XDG_RUNTIME_DIR')
    def digest(path):
        with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
    binary = digest(args.executable)
    sources = {name: digest(repo / name) for name in ('src/model.zi', 'src/app_host.zi', 'ziran.toml', 'ziran.lock', 'tests/tabs_test.py')}
    root = repo / 'build/tabs-ui-fixture'
    shutil.rmtree(root, ignore_errors=True); root.mkdir(mode=0o700)
    paths = [root]
    for name in ['a/same é', 'b/same é', 'unicode-世界', r'literal-\xFF', 'long-' + 'é' * 90,
                 *[f'group-{i}/folder-{i}' for i in range(10)]]:
        path = root / name; path.mkdir(parents=True); (path / 'zz-proof.txt').write_text(name); paths.append(path)
    (root / 'zz-proof.txt').write_text('home')
    raw = os.fsencode(root) + b'/raw-\xff\n'
    os.mkdir(raw)
    env = dict(os.environ, HOME=str(root))
    log = (root / 'app.log').open('wb')
    proc = subprocess.Popen([str(args.executable)], cwd=root, env=env, stdout=log, stderr=log)
    peer = None; captures = []; passed = False
    try:
        def xdo(*parts):
            assert proc.poll() is None, f'Explorer exited {proc.returncode}'
            return subprocess.run(['xdotool', *map(str, parts)], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
        deadline = time.monotonic() + 15; window = None
        while time.monotonic() < deadline:
            found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(proc.pid)], capture_output=True, text=True)
            if found.returncode == 0: window = found.stdout.splitlines()[0]; break
            assert proc.poll() is None; time.sleep(.05)
        assert window; xdo('windowfocus', '--sync', window); time.sleep(.5)
        def key(*parts):
            for part in parts: xdo('key', '--clearmodifiers', part); time.sleep(.12)
        def offer(text):
            nonlocal peer
            if peer:
                if peer.poll() is None: peer.terminate()
                peer.wait(timeout=10); peer.stdout.close()
            payload = root / 'payload'; payload.write_text(text)
            peer = subprocess.Popen([sys.executable, str(repo / 'tests/file_clipboard_test.py'), '--offer', 'UTF8_STRING', str(payload)], stdout=subprocess.PIPE, stderr=log)
            assert select.select([peer.stdout], [], [], 10)[0] and peer.stdout.readline().strip() == b'READY'
        def edit(text): offer(text); key('ctrl+l', 'ctrl+a', 'ctrl+v')
        def navigate(text): edit(text); key('Return')
        def field():
            key('ctrl+a', 'ctrl+c')
            return subprocess.check_output([sys.executable, str(repo / 'tests/file_clipboard_test.py'), '--read', 'UTF8_STRING'], timeout=15).decode()
        def cwd():
            key('ctrl+l'); value = field(); key('Escape'); return value
        def capture(suffix):
            path = repo / 'build' / f'{args.capture_prefix}-{suffix}.png'
            subprocess.run(['import', '-window', window, str(path)], check=True, capture_output=True, timeout=10)
            captures.append({'path': str(path), 'sha256': digest(path), 'mtime_ns': path.stat().st_mtime_ns})
        for path in paths[1:]: key('ctrl+t'); navigate(str(path))
        assert cwd() == str(paths[-1]); capture('overflow-last')
        key('ctrl+Tab'); assert cwd() == str(root); capture('overflow-first')
        key('ctrl+shift+Tab'); assert cwd() == str(paths[-1])
        key('ctrl+shift+Prior'); assert cwd() == str(paths[-1]); capture('keyboard-reordered')
        # Reveal the first tab, then drag it across two neighbours. The native
        # widget decides the target; the complete cycle proves no identities lost.
        for _ in paths:
            if cwd() == str(root): break
            key('ctrl+Prior')
        assert cwd() == str(root)
        key('ctrl+Prior'); assert cwd() == str(paths[-2]), 'adjacent tabs must wrap like native Thunar'
        key('ctrl+Next'); assert cwd() == str(root)
        before_drag = []
        for _ in paths: before_drag.append(cwd()); key('ctrl+Tab')
        assert cwd() == str(root)
        xdo('mousemove', '--window', window, 230, 81); xdo('mousedown', 1)
        time.sleep(.15); xdo('mousemove', '--window', window, 560, 81); time.sleep(.25)
        capture('dragging'); xdo('mouseup', 1); time.sleep(.25)
        assert cwd() == str(root); capture('pointer-reordered')
        observed = []
        for _ in paths: observed.append(cwd()); key('ctrl+Tab')
        assert Counter(observed) == Counter(map(str, paths)), observed
        assert observed != before_drag, 'native drag did not reorder the first tab'
        # Wheel overflow must remain usable independently of active-tab reveal.
        xdo('mousemove', '--window', window, 650, 81); xdo('click', '--repeat', 8, '--delay', 60, 5)
        time.sleep(.2); capture('wheel-overflow')
        before = cwd(); edit('missing'); key('ctrl+Tab')
        assert field() == 'missing', 'tab shortcut stole editor input'; key('Escape'); assert cwd() == before
        xdo('windowsize', window, 560, 600); time.sleep(.3); capture('narrow-overflow')
        key('ctrl+l'); capture('narrow-editor'); key('Escape')
        for _ in range(len(paths) - 1): key('ctrl+w')
        capture('last-tab')
        navigate(str(paths[1])); key('ctrl+t'); navigate(str(paths[2]))
        shutil.rmtree(paths[1]); key('ctrl+w'); assert cwd() == str(paths[2]); capture('failed-close')
        paths[1].mkdir(); key('ctrl+w'); assert cwd() == str(paths[1])
        key('ctrl+t'); navigate(str(root)); edit('raw-'); key('End', 'Tab')
        assert field() == r'raw-\xFF\x0A/'
        key('Return'); assert cwd().endswith(r'raw-\xFF\x0A'); capture('raw-label')
        key('ctrl+Tab'); assert cwd() == str(paths[1]); key('ctrl+shift+Tab')
        assert cwd().endswith(r'raw-\xFF\x0A')
        key('ctrl+w'); capture('last-tab-before-close')
        key('ctrl+w'); assert proc.wait(timeout=10) == 0, 'Ctrl+W must close the final window'
        passed = True
        print('Native16+ labeled tabs/duplicate-Unicode-long-raw labels/overflow/drag/keyboard/close/modal/narrow tests passed', flush=True)
    finally:
        if peer:
            if peer.poll() is None: peer.terminate()
            peer.wait(timeout=10); peer.stdout.close()
        if proc.poll() is None: proc.terminate()
        proc.wait(timeout=10); log.close()
        after = digest(args.executable)
        assert binary == after, 'tested executable changed'
        for name, wanted in sources.items(): assert digest(repo / name) == wanted, name
        receipt = repo / 'build' / f'{args.capture_prefix}-receipt.json'
        receipt.write_text(json.dumps({'passed': passed, 'executable': str(args.executable), 'binary_sha256': binary,
                                      'binary_after_sha256': after, 'source_boundary': sources, 'captures': captures}, indent=2) + '\n')
        receipt.chmod(0o600)


if __name__ == '__main__': main()
