#!/usr/bin/env python3
"""Private native dual-pane actions, clipboard, scopes, resizing and captures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time
from ui_test import menu_action, wait_for


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path, default=repo / 'build/explorer-desktop')
    parser.add_argument('--capture-prefix', default='split')
    args = parser.parse_args()
    assert os.environ.get('DISPLAY') and os.environ.get('XDG_RUNTIME_DIR')
    def digest(path):
        with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
    binary = digest(args.executable)
    sources = {name: digest(repo / name) for name in ('src/model.zi', 'src/app_host.zi', 'src/desktop_file_clipboard.zi', 'ziran.toml', 'ziran.lock', 'tests/split_test.py')}
    root = repo / 'build/split-ui-fixture'
    shutil.rmtree(root, ignore_errors=True); root.mkdir(mode=0o700)
    a, b, external, target = (root / name for name in ('a/same é', 'b/same é', 'external', 'thunar-target'))
    for path in (a, b, external, target): path.mkdir(parents=True)
    special = 'copy-é 世界\n%#?.txt'
    (a / special).write_text('original Unicode newline')
    (b / 'reverse.src').write_text('reverse cut')
    (external / 'thunar.txt').write_text('external peer')
    popup_b = root / 'popup-B'; popup_b.mkdir()
    for i in range(100): (a / f'file-{i:03d}').write_text(str(i))
    log = (root / 'app.log').open('wb')
    proc = subprocess.Popen([str(args.executable)], cwd=root, env=dict(os.environ, HOME=str(root)), stdout=log, stderr=log)
    peer = None; thunar = None; captures = []; passed = False
    try:
        def xdo(*parts):
            assert proc.poll() is None, f'Explorer exited {proc.returncode}'
            return subprocess.run(['xdotool', *map(str, parts)], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
        def find(pid):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(pid)], capture_output=True, text=True)
                if result.returncode == 0: return result.stdout.splitlines()[0]
                time.sleep(.05)
            raise AssertionError('native window timeout')
        window = find(proc.pid)
        xdo('windowfocus', '--sync', window); time.sleep(.3)
        def key(*parts, win=None):
            xdo('windowraise', win or window); xdo('windowfocus', '--sync', win or window)
            for part in parts: xdo('key', '--clearmodifiers', part); time.sleep(.12)
        def click(x, y):
            xdo('windowraise', window); xdo('windowfocus', '--sync', window); xdo('mousemove', '--window', window, x, y); xdo('click', 1); time.sleep(.16)
        def offer(text):
            nonlocal peer
            if peer:
                if peer.poll() is None: peer.terminate()
                peer.wait(timeout=10); peer.stdout.close()
            payload = root / 'payload'; payload.write_text(text)
            peer = subprocess.Popen([sys.executable, str(repo / 'tests/file_clipboard_test.py'), '--offer', 'UTF8_STRING', str(payload)], stdout=subprocess.PIPE, stderr=log)
            assert select.select([peer.stdout], [], [], 10)[0] and peer.stdout.readline().strip() == b'READY'
        def edit(text): offer(text); key('ctrl+l', 'ctrl+a', 'ctrl+v')
        def navigate(text): edit(str(text)); key('Return')
        def field():
            key('ctrl+a', 'ctrl+c')
            return subprocess.check_output([sys.executable, str(repo / 'tests/file_clipboard_test.py'), '--read', 'UTF8_STRING'], timeout=15).decode()
        def cwd():
            key('ctrl+l'); value = field(); key('Escape'); return value
        def other(): menu_action(xdo, window, "View", 7)
        def capture(suffix):
            xdo('windowraise', window); time.sleep(.1)
            path = repo / 'build' / f'{args.capture_prefix}-{suffix}.png'
            subprocess.run(['import', '-window', window, str(path)], check=True, capture_output=True, timeout=10)
            captures.append({'path': str(path), 'sha256': digest(path), 'mtime_ns': path.stat().st_mtime_ns})
        navigate(a); key('ctrl+2', 'F3'); assert cwd() == str(a); capture('left-active')
        other(); navigate(b); assert cwd() == str(b); capture('right-active')
        other(); assert cwd() == str(a)
        # The newline/Unicode file is selected by its visible sorted identity.
        key('Home', 'ctrl+c')
        advertised = subprocess.check_output([sys.executable, str(repo / 'tests/file_clipboard_test.py'), '--read', 'x-special/gnome-copied-files'], timeout=15)
        assert (a / special).as_uri().encode() in advertised.splitlines(), advertised
        capture('source-selected')
        other(); capture('destination-before-paste')
        retained = subprocess.check_output([sys.executable, str(repo / 'tests/file_clipboard_test.py'), '--read', 'x-special/gnome-copied-files'], timeout=15)
        assert retained == advertised, (advertised, retained)
        key('ctrl+v')
        wait_for(lambda: (b / special).exists(), 'cross-pane clipboard copy completion', proc)
        capture('paste-result')
        assert (b / special).read_text() == 'original Unicode newline' and (a / special).exists()
        key('End', 'ctrl+x'); other(); key('ctrl+v')
        wait_for(lambda: (a / 'reverse.src').exists() and not (b / 'reverse.src').exists(), 'cross-pane clipboard cut completion', proc)
        assert (a / 'reverse.src').read_text() == 'reverse cut' and not (b / 'reverse.src').exists()
        key('ctrl+v'); assert len(list(a.glob('reverse*'))) == 1
        capture('cross-pane-clipboard')
        # Incoming Thunar copy goes into the active RIGHT pane; no second host or owner is used.
        other()
        thunar = subprocess.Popen(['thunar', str(external)], env=dict(os.environ, HOME=str(root)), stdout=log, stderr=log)
        tw = find(thunar.pid)
        # A visible native window may precede its asynchronous directory load.
        # Wait for the exact URI offer before testing the receiving pane.
        deadline = time.monotonic() + 10
        expected_uri = (external / 'thunar.txt').as_uri().encode()
        while True:
            key('ctrl+a', 'ctrl+c', win=tw)
            advertised = subprocess.run([sys.executable, str(repo / 'tests/file_clipboard_test.py'),
                                         '--read', 'x-special/gnome-copied-files'],
                                        capture_output=True, timeout=15)
            if advertised.returncode == 0 and expected_uri in advertised.stdout.splitlines():
                break
            assert time.monotonic() < deadline, 'Thunar did not offer the loaded fixture file'
        key('ctrl+v')
        deadline = time.monotonic() + 10
        while not (b / 'thunar.txt').exists() and time.monotonic() < deadline: time.sleep(.05)
        assert (b / 'thunar.txt').read_text() == 'external peer' and not (a / 'thunar.txt').exists()
        # Outgoing cut from the right pane is pasted by the actual installed Thunar.
        key('End', 'ctrl+x')
        key('ctrl+l', 'ctrl+a', win=tw)
        xdo('type', '--clearmodifiers', '--delay', 1, str(target)); key('Return', 'ctrl+v', win=tw)
        deadline = time.monotonic() + 10
        while not (target / 'thunar.txt').exists() and time.monotonic() < deadline: time.sleep(.05)
        assert (target / 'thunar.txt').read_text() == 'external peer' and not (b / 'thunar.txt').exists()
        # Input returns to the correct pane, with independent histories/tabs/settings.
        key('ctrl+3'); capture('compact-right')
        other(); key('ctrl+1'); capture('icon-left')
        key('ctrl+2')
        for _ in range(10): key('ctrl+t')
        capture('tab-overflow-left')
        other(); assert cwd() == str(b); key('ctrl+t'); navigate(external)
        key('ctrl+Tab'); assert cwd() == str(b)
        other(); assert cwd() == str(a)
        # Genuine divider pointer drag and wheel scrolling in an inactive pane.
        xdo('windowraise', window); xdo('windowfocus', '--sync', window)
        geometry = dict(line.split('=', 1) for line in xdo('getwindowgeometry', '--shell', window).splitlines())
        divider_x = 170 + (int(geometry['WIDTH']) - 170) // 2
        xdo('mousemove', '--window', window, divider_x, 360); xdo('mousedown', 1); time.sleep(.15)
        xdo('mousemove', '--window', window, divider_x + 90, 360); time.sleep(.15); xdo('mouseup', 1); time.sleep(.2)
        assert cwd() == str(a), 'divider drag changed the active pane'
        capture('divider-dragged')
        xdo('mousemove', '--window', window, 300, 400); xdo('click', '--repeat', 8, '--delay', 40, 5)
        time.sleep(.2); capture('list-scrolled')
        key('ctrl+l'); capture('location-left'); key('Tab', 'Escape')
        # Regression: an open action menu owns tab A while Ctrl+Tab arrives.
        key('ctrl+t'); navigate(popup_b); key('ctrl+shift+Tab'); assert cwd() == str(a)
        xdo('windowsize', window, 560, 600); time.sleep(.2)
        menu_action(xdo, window, "File"); key('ctrl+Tab', 'Home', 'Return')
        offer('popup-owned'); key('ctrl+v', 'Return')
        assert (a / 'popup-owned').is_dir() and not (popup_b / 'popup-owned').exists(), 'open Actions retargeted its command to tab B'
        capture('popup-owner')
        xdo('windowsize', window, 960, 600); time.sleep(.2)
        key('F3'); assert cwd() == str(a); capture('collapsed-left')
        key('F3'); other(); assert cwd() == str(b)
        key('F3'); assert cwd() == str(b); capture('collapsed-right')
        key('F3'); assert cwd() == str(b)
        xdo('windowsize', window, 560, 600); time.sleep(.3); capture('narrow')
        key('ctrl+l'); capture('narrow-editor'); key('Escape')
        menu_action(xdo, window, "File"); capture('narrow-actions'); key('Escape')
        xdo('windowsize', window, 440, 600); time.sleep(.2); capture('small-embedded-width')
        key('ctrl+l'); capture('small-editor'); key('Escape')
        # Retained peer disappearance must reject re-enabling without falling back to root.
        key('F3'); shutil.rmtree(a); key('F3'); assert cwd() == str(b); capture('retained-error')
        passed = True
        print('Native split F3/active ownership/tabs/three views/drag/scroll/Unicode-newline clipboard both ways/actual Thunar/narrow/modal/retained failure passed', flush=True)
    finally:
        for child in (peer, thunar, proc):
            if child:
                if child.poll() is None: child.terminate()
                child.wait(timeout=10)
                if child is peer: child.stdout.close()
        log.close()
        after = digest(args.executable); assert after == binary
        for name, wanted in sources.items(): assert digest(repo / name) == wanted, name
        receipt = repo / 'build' / f'{args.capture_prefix}-receipt.json'
        receipt.write_text(json.dumps({'passed': passed, 'executable': str(args.executable), 'binary_sha256': binary, 'binary_after_sha256': after, 'source_boundary': sources, 'captures': captures}, indent=2) + '\n')
        receipt.chmod(0o600)

if __name__ == '__main__': main()
