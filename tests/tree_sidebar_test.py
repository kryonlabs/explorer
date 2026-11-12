#!/usr/bin/env python3
"""Exercise the native local tree on an isolated display; no owner desktop."""
import argparse
import os
from pathlib import Path
import shutil
import select
import subprocess
import sys
import time
from ui_test import menu_action
from PIL import Image, ImageChops


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path, default=repo / 'build/explorer-desktop')
    parser.add_argument('--capture-prefix', default='tree')
    options = parser.parse_args()
    assert os.environ.get('DISPLAY') and os.environ.get('XDG_RUNTIME_DIR')
    root = repo / 'build/tree-ui-fixture'
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(mode=0o700)
    alpha = root / 'alpha space\né'; alpha.mkdir()
    bravo = root / 'bravo'; bravo.mkdir()
    hidden = root / '.hidden'; hidden.mkdir()
    raw = os.fsencode(root) + b'/raw-\xff'; os.mkdir(raw)
    (alpha / 'loop').symlink_to(root, target_is_directory=True)
    for folder in (os.fsencode(alpha), os.fsencode(bravo), os.fsencode(hidden), raw):
        with open(folder + b'/zz-proof.txt', 'wb') as stream:
            stream.write(b'proof')
    captured = root / 'opened-path'
    env = os.environ.copy()
    env.update(HOME=str(root), KRYON_TEST_OPEN_URI_CAPTURE=str(captured))
    process = None
    window = None
    log = (root / 'app.log').open('wb')
    try:
        process = subprocess.Popen([str(options.executable)], cwd=root, env=env, stdout=log, stderr=log)
        def healthy():
            assert process.poll() is None, f'Explorer exited {process.returncode}; see {root / "app.log"}'
        def xdo(*args):
            healthy()
            return subprocess.run(['xdotool', *map(str, args)], check=True,
                                  capture_output=True, text=True, timeout=10).stdout.strip()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(process.pid)],
                                   capture_output=True, text=True)
            if found.returncode == 0:
                window = found.stdout.splitlines()[0]
                xdo('windowfocus', '--sync', window)
                time.sleep(.8)
                break
            healthy(); time.sleep(.05)
        assert window, 'missing owned Explorer window'
        def key(*items):
            for item in items:
                xdo('key', '--clearmodifiers', item); time.sleep(.2); healthy()
        def click(x, y):
            xdo('mousemove', '--window', window, x, y); xdo('click', '1')
            time.sleep(.3); healthy()
        def opened(folder, name=b'zz-proof.txt'):
            key('ctrl+2', 'End', 'Return')
            assert captured.read_bytes() == os.fsencode(folder) + b'/' + name, captured.read_bytes()
        def capture(suffix):
            target = repo / 'build' / (options.capture_prefix + '-' + suffix + '.png')
            subprocess.run(['import', '-window', window,
                            str(target)],
                           check=True, capture_output=True, timeout=10)
            return target

        key('ctrl+e')
        click(14, 181)  # Home disclosure; cwd remains the fixture root.
        capture('expanded')
        click(107, 213)  # Unicode/newline folder label.
        opened(alpha)
        (alpha / 'zzz-refreshed.txt').write_text('new')
        click(107, 213)  # Already-selected label must activate and refresh again.
        opened(alpha, b'zzz-refreshed.txt')
        click(32, 213)  # Expand alpha, then refuse the loop to Home.
        click(50, 245)
        capture('cycle-error')
        opened(alpha, b'zzz-refreshed.txt')
        click(32, 213)  # Collapse alpha, restoring direct-child rows.
        click(107, 245)
        opened(bravo)
        click(107, 277)
        opened(raw)
        # Ctrl+E preserves Places as the default alternative; Ctrl+B also
        # returns there. Bookmarks are retained across each switch.
        key('ctrl+b'); capture('places')
        key('ctrl+e')
        menu_action(xdo, window, "View", 3)  # Hidden applies to the tree: hidden is the first child.
        click(107, 213)
        opened(hidden)
        capture('hidden')
        key('ctrl+e', 'ctrl+e', 'ctrl+b')
        healthy()
        # Start in a deep cwd: automatic reveal must show its marker and label
        # without a preceding tree key event. Each ancestor has a file whose
        # captured open path proves subsequent keyboard navigation.
        deep = root / 'deep'; deep.mkdir()
        for _ in range(12):
            (deep / 'zz-proof.txt').write_text('ancestor')
            deep = deep / 'd'; deep.mkdir()
        (deep / 'zz-proof.txt').write_text('parent')
        target = deep / 'long Unicode folder é with a long label'; target.mkdir()
        (target / 'zz-proof.txt').write_text('deep')
        process.terminate(); process.wait(timeout=10)
        process = subprocess.Popen([str(options.executable)], cwd=target, env=env, stdout=log, stderr=log)
        window = None
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(process.pid)],
                                   capture_output=True, text=True)
            if found.returncode == 0:
                window = found.stdout.splitlines()[0]
                xdo('windowfocus', '--sync', window); time.sleep(.8); break
            healthy(); time.sleep(.05)
        assert window, 'missing owned deep Explorer window'
        payload = root / 'tree-location-payload'
        payload.write_text(str(target))
        peer = subprocess.Popen([sys.executable, str(repo / 'tests/file_clipboard_test.py'),
                                 '--offer', 'UTF8_STRING', str(payload)], stdout=subprocess.PIPE, stderr=log)
        try:
            assert select.select([peer.stdout], [], [], 10)[0], 'native text peer did not become ready'
            assert peer.stdout.readline().strip() == b'READY'
            key('ctrl+l', 'ctrl+a', 'ctrl+v', 'Return')
        finally:
            peer.terminate(); peer.wait(timeout=10); peer.stdout.close()
        key('ctrl+e')
        before = capture('deep-reveal')
        click(40, 575)
        after = capture('deep-left')
        with Image.open(before) as a, Image.open(after) as b:
            assert ImageChops.difference(a.crop((8, 133, 158, 558)), b.crop((8, 133, 158, 558))).getbbox(), 'horizontal button did not move tree content'
        click(115, 575)
        key('ctrl+e', 'ctrl+e', 'Left', 'Return')
        opened(deep)
        key('ctrl+e', 'ctrl+e', 'Right', 'Return')
        opened(target)
        capture('deep-keyboard')
        print('Explorer native tree toggle/disclosure/repeated activation/raw/hidden/cycle GUI tests passed', flush=True)
    except Exception:
        if window and process.poll() is None:
            subprocess.run(['import', '-window', window, str(root / 'failure.png')], capture_output=True, timeout=10)
        raise
    finally:
        if process and process.poll() is None:
            process.terminate()
        if process:
            process.wait(timeout=10)
        log.close()


if __name__ == '__main__':
    main()
