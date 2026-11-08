#!/usr/bin/env python3
"""Native location entry and breadcrumbs, confined to private_desktop.py."""
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


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path, default=repo / 'build/shelf-desktop')
    parser.add_argument('--capture-prefix', default='location')
    args = parser.parse_args()
    assert os.environ.get('DISPLAY') and os.environ.get('XDG_RUNTIME_DIR')
    def digest(path):
        with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
    binary_before = digest(args.executable)
    source_boundary = {name: digest(repo / name) for name in ('src/model.zi', 'src/app_host.zi', 'src/location.zi', 'ziran.toml', 'ziran.lock', 'tests/location_test.py')}
    captures = []; passed = False
    root = repo / 'build/location-ui-fixture'
    shutil.rmtree(root, ignore_errors=True); root.mkdir(mode=0o700)
    names = ['alpha space', 'alpine', r'literal-\x41', 'line\né', 'unicode-é']
    folders = [root / name for name in names]
    raw = os.fsencode(root) + b'/raw-\xff'
    for path in folders: path.mkdir()
    os.mkdir(raw)
    for path in [os.fsencode(root), *(os.fsencode(p) for p in folders), raw]:
        with open(path + b'/zz-proof.txt', 'wb') as stream: stream.write(b'proof')
    (root / 'alps.txt').write_text('file location must select without opening')
    captured = root / 'opened-path'
    env = dict(os.environ, HOME=str(root), KRYON_TEST_OPEN_URI_CAPTURE=str(captured))
    log = (root / 'app.log').open('wb')
    proc = subprocess.Popen([str(args.executable)], cwd=root, env=env, stdout=log, stderr=log)
    peer = None; window = None
    try:
        def healthy():
            assert proc.poll() is None, f'Shelf exited {proc.returncode}; see {root / "app.log"}'
        def xdo(*parts):
            healthy()
            return subprocess.run(['xdotool', *map(str, parts)], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(proc.pid)], capture_output=True, text=True)
            if found.returncode == 0:
                window = found.stdout.splitlines()[0]; break
            healthy(); time.sleep(.05)
        assert window, 'missing owned Shelf window'
        xdo('windowfocus', '--sync', window); time.sleep(.6)
        def key(*parts):
            for part in parts: xdo('key', '--clearmodifiers', part); time.sleep(.15); healthy()
        def offer(text):
            nonlocal peer
            if peer:
                if peer.poll() is None: peer.terminate()
                peer.wait(timeout=10); peer.stdout.close()
            payload = root / 'input-payload'; payload.write_text(text)
            peer = subprocess.Popen([sys.executable, str(repo / 'tests/file_clipboard_test.py'), '--offer', 'UTF8_STRING', str(payload)], stdout=subprocess.PIPE, stderr=log)
            assert select.select([peer.stdout], [], [], 10)[0] and peer.stdout.readline().strip() == b'READY'
        def edit(text):
            offer(text); key('ctrl+l', 'ctrl+a', 'ctrl+v')
        def field():
            key('ctrl+a', 'ctrl+c')
            return subprocess.check_output([sys.executable, str(repo / 'tests/file_clipboard_test.py'), '--read', 'UTF8_STRING'], timeout=15).decode()
        def navigate(text): edit(text); key('Return')
        def opened(path, name=b'zz-proof.txt'):
            key('ctrl+2', 'End', 'Return')
            expected = os.fsencode(path) + b'/' + name
            assert captured.read_bytes() == expected, (captured.read_bytes(), expected)
        def capture(suffix):
            path = repo / 'build' / f'{args.capture_prefix}-{suffix}.png'
            subprocess.run(['import', '-window', window, str(path)], check=True, capture_output=True, timeout=10)
            captures.append({'path': str(path), 'sha256': digest(path), 'mtime_ns': path.stat().st_mtime_ns})
        edit('al'); key('End', 'Tab'); assert field() == 'alp'
        key('Down'); assert field() == 'alpha space/'
        key('Down'); assert field() == 'alpine/'
        key('Up'); assert field() == 'alpha space/'
        capture('completion'); key('Escape'); opened(root)
        prior = captured.read_bytes()
        navigate('alps.txt'); assert captured.read_bytes() == prior, 'file location executed instead of selecting'
        key('Return'); assert captured.read_bytes() == os.fsencode(root / 'alps.txt')
        edit('missing'); key('Return'); assert field() == 'missing'
        capture('error'); key('Escape', 'Return'); assert captured.read_bytes() == os.fsencode(root / 'alps.txt')
        navigate('alpha space'); opened(folders[0])
        navigate('../alpine'); opened(folders[1])
        navigate('~'); opened(root)
        navigate(r'literal-\x41'); opened(folders[2])
        navigate('~')
        edit('raw-'); key('End', 'Tab'); assert field() == r'raw-\xFF/'
        key('Return'); opened(raw)
        # Reopen while in a raw cwd: editing remains explicitly escaped.
        key('ctrl+l'); assert r'raw-\xFF' in field(); key('Escape')
        navigate('~')
        edit('line'); key('End', 'Tab'); assert field() == 'line\\x0Aé/'
        key('Return'); opened(folders[3])
        navigate('~')
        edit('uni'); key('End', 'Tab'); assert field() == 'unicode-é/'
        key('Return'); opened(folders[4])
        deep = root / 'deep'; deep.mkdir()
        for index in range(8): deep = deep / f'long ancestor {index} é'; deep.mkdir()
        (deep / 'zz-proof.txt').write_text('deep')
        navigate(str(deep)); opened(deep); capture('breadcrumbs')
        xdo('windowsize', window, 560, 600); time.sleep(.4)
        key('ctrl+l'); assert field() == str(deep); capture('narrow-editor'); key('Escape')
        capture('narrow-breadcrumbs')
        # Overflow owns the left of the full-width row; Home picks filesystem root.
        xdo('mousemove', '--window', window, 40, 108); xdo('click', '1'); time.sleep(.3)
        key('Home', 'Return')
        key('ctrl+l'); assert field() == '/', 'breadcrumb overflow did not activate root'
        key('Escape'); navigate(str(root)); opened(root)
        xdo('mousemove', '--window', window, 500, 26); xdo('click', '1'); time.sleep(.3)
        capture('narrow-actions-open'); key('Home'); capture('narrow-actions-home'); key('Return'); capture('narrow-actions-commit')
        xdo('type', '--clearmodifiers', '--delay', 15, 'from-narrow-actions'); key('Return')
        assert (root / 'from-narrow-actions').is_dir(), 'narrow actions keyboard menu lost folder creation'
        passed = True
        print('Shelf native location common-prefix/cycling/cancel/file/relative/home/raw/Unicode/errors/narrow/breadcrumb tests passed', flush=True)
    except Exception:
        if window and proc.poll() is None:
            subprocess.run(['import', '-window', window, str(root / 'failure.png')], capture_output=True, timeout=10)
        raise
    finally:
        if peer:
            if peer.poll() is None: peer.terminate()
            peer.wait(timeout=10); peer.stdout.close()
        if proc.poll() is None: proc.terminate()
        proc.wait(timeout=10); log.close()
        binary_after = digest(args.executable)
        receipt = {'executable': str(args.executable.resolve()), 'binary_sha256': binary_before,
                   'binary_after_sha256': binary_after, 'passed': passed and binary_before == binary_after,
                   'source_boundary': source_boundary, 'captures': captures}
        receipt_path = repo / 'build' / f'{args.capture_prefix}-receipt.json'
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n'); receipt_path.chmod(0o600)
        if passed:
            assert binary_before == binary_after, 'executable changed during private location GUI test'
            print(f'Location GUI binary SHA256 {binary_before}; receipt {receipt_path}', flush=True)


if __name__ == '__main__': main()
