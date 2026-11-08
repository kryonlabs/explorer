#!/usr/bin/env python3
"""Exercise raw Linux filename bytes only on a private desktop."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import time


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path, default=repo / 'build/shelf-desktop')
    options = parser.parse_args()
    assert os.environ.get('DISPLAY') and os.environ.get('XDG_RUNTIME_DIR')
    root = repo / 'build/filename-fixture'
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(mode=0o700)
    source = root / 'names'; source.mkdir()
    raw_dir = os.fsencode(source) + b'/01-dir-\x80'
    raw_file = os.fsencode(source) + b'/02-bad-\xff\xfe.txt'
    literal_file = source / r'02-bad-\xFF\xFE.txt'
    os.mkdir(raw_dir)
    for path in (raw_file, raw_dir + b'/child-\xff.txt'):
        with open(path, 'wb') as stream:
            stream.write(b'raw filename fixture')
    shutil.copyfile(os.fsencode(repo / 'assets/icons/ui.webp'), raw_dir + b'/image-\xff.webp')
    literal_file.write_text('literal escape fixture')
    captured = root / 'opened-path'
    env = os.environ.copy()
    env['KRYON_TEST_OPEN_URI_CAPTURE'] = str(captured)
    log = (root / 'app.log').open('wb')
    process = subprocess.Popen([str(options.executable)], cwd=root, env=env,
                               stdout=log, stderr=log)
    try:
        def healthy():
            assert process.poll() is None, f'Shelf exited {process.returncode}; see {root / "app.log"}'
        def xdo(*args):
            healthy()
            return subprocess.run(['xdotool', *map(str, args)], capture_output=True,
                                  text=True, check=True, timeout=10).stdout.strip()
        window = None
        deadline = time.monotonic() + 15
        while not window and time.monotonic() < deadline:
            result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(process.pid)],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                window = result.stdout.splitlines()[0]
            else:
                healthy(); time.sleep(.05)
        assert window, 'missing owned Shelf window'
        xdo('windowfocus', '--sync', window)
        def key(*keys):
            for item in keys:
                xdo('key', '--clearmodifiers', item)
                time.sleep(.15)
                healthy()
        def navigate(path):
            key('ctrl+l', 'ctrl+a')
            xdo('type', '--clearmodifiers', '--delay', '1', path)
            key('Return')
            time.sleep(.3); healthy()
        def opened(expected):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                healthy()
                if captured.exists() and captured.read_bytes() == expected:
                    return
                time.sleep(.05)
            raise AssertionError(f'expected exact opened bytes {expected!r}')
        navigate(source)  # Before the fix, this poisons the text frame and exits.
        for view in ('ctrl+1', 'ctrl+2', 'ctrl+3'):
            key(view, 'Home', 'Return')
            key('ctrl+l', 'Return')  # Unchanged escaped current path must round-trip.
            key('Home', 'Return')
            opened(raw_dir + b'/child-\xff.txt')
            navigate(source)
            print(view + ' raw directory/current path/file opening passed', flush=True)
        # Exact raw names survive internal duplication. Desktop export stays rejected.
        key('ctrl+2', 'Home', 'Down', 'Down', 'Return')
        opened(raw_file)
        geometry = dict(line.split('=', 1) for line in xdo('getwindowgeometry', '--shell', window).splitlines())
        width = int(geometry['WIDTH'])
        # Rename opens lossless byte escapes. Return unchanged must keep raw bytes.
        xdo('mousemove', '--window', window, width - 165, 26); xdo('click', '1')
        time.sleep(.15); key('Return')
        assert os.path.exists(raw_file) and literal_file.exists()
        # Preserve the invalid suffix while editing the name through escaped text.
        xdo('mousemove', '--window', window, width - 165, 26); xdo('click', '1')
        time.sleep(.15); key('ctrl+a')
        xdo('type', '--clearmodifiers', '--delay', '1', r'\xGG')
        key('Return')
        assert os.path.exists(raw_file) and literal_file.exists()
        key('ctrl+a')
        xdo('type', '--clearmodifiers', '--delay', '1', r'04-renamed-\xFF\xFE.txt')
        key('Return')
        renamed = os.fsencode(source) + b'/04-renamed-\xff\xfe.txt'
        assert os.path.exists(renamed) and not os.path.exists(raw_file)
        # Refresh resets selection. Select and open the renamed entry explicitly.
        key('End', 'Return')
        opened(renamed)
        xdo('mousemove', '--window', window, 90, 68); xdo('click', '1')
        time.sleep(.3); healthy()
        duplicated = os.fsencode(source) + b'/04-renamed-\xff\xfe (2).txt'
        assert os.path.exists(duplicated) and os.path.exists(renamed)
        assert literal_file.read_text() == 'literal escape fixture'
        key('ctrl+c')  # Unrepresentable desktop publication is an error, not a crash.
        healthy()
        print('raw-byte rename, unchanged prompt, duplicate and rejected desktop copy passed')
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
        log.close()


if __name__ == '__main__':
    main()
