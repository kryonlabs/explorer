#!/usr/bin/env python3
"""Exercise Explorer with an owned fixture in a private 32 MiB Taiji desktop."""
import io
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from PIL import Image, ImageChops

from private_desktop import taiji_staging


def call(*args, check=True):
    return subprocess.run(args, capture_output=True, check=check, timeout=5).stdout


def until(predicate, message, timeout=16):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.15)
    raise AssertionError(message)


def main():
    assert os.environ.get('EXPLORER_PRIVATE_DESKTOP') == '1'
    assert os.environ.get('HARMONY_DESKTOP_RECOVERY') == '0'
    root = Path(os.environ.get('TAIJIOS_ROOT', '../../taijiosnet/taijios')).resolve()
    emulator = Path(os.environ.get('TAIJIOS_EMULATOR', root / 'emu/Linux/o.emu'))
    staging = taiji_staging(root)
    with tempfile.TemporaryDirectory(dir=staging, prefix='explorer-gui-') as directory:
        fixture = Path(directory)
        guest = '/' + fixture.relative_to(root).as_posix()
        bundle = os.environ.get('EXPLORER_TAIJI_TEST_BUNDLE', 'build/explorer.zx')
        shutil.copyfile(bundle, fixture/'explorer.zx')
        (fixture/'target').mkdir()
        (fixture/'zz-sample.txt').write_text('Explorer guest preview content\n')
        for i in range(int(os.environ.get('EXPLORER_TAIJI_ROWS', '80'))):
            (fixture/f'row-{i:02d}.txt').touch()
        memory_report = ''
        if os.environ.get('EXPLORER_TAIJI_REPORT_MEMORY') == '1':
            memory_report = 'echo EXPLORER_GUEST_POOLS_LIVE_LIMIT_HIGH_WATER; cat /dev/memory; '
        desktop = (f'home={guest}; wm/toolbar &; zxrun -w {guest}/explorer.zx; '
                   f'echo EXPLORER_EXIT $status; {memory_report}sleep 60')
        command = ['wm/wm', '/zx/sh.dis', '-c', desktop]
        overlay = os.environ.get('EXPLORER_TAIJI_ZX_OVERLAY') or os.environ.get('EXPLORER_TAIJI_DIS_OVERLAY')
        if overlay:
            # A separately staged set of guest modules must match the candidate emulator.
            assert overlay.startswith('/build/zx-smoke/') and all(c.isascii() and (c.isalnum() or c in '/-_.') for c in overlay)
            assert '..' not in Path(overlay).parts and (root / overlay.lstrip('/')).is_dir()
            bind = '; '.join(f'bind -b {overlay} {destination}' for destination in ('/zx', '/zx/wm', '/zx/lib'))
            command = ['/zx/sh.dis', '-c', f"{bind}; wm/wm /zx/sh.dis -c '{desktop}'"]
        with tempfile.TemporaryFile() as log:
            def log_tail():
                length = os.fstat(log.fileno()).st_size
                return os.pread(log.fileno(), 8192, max(0, length - 8192))

            def log_contains(needle):
                offset = 0
                previous = b''
                while chunk := os.pread(log.fileno(), 8192, offset):
                    if needle in previous + chunk:
                        return True
                    previous = chunk[-(len(needle) - 1):]
                    offset += len(chunk)
                return False

            proc = subprocess.Popen([emulator, '-p', 'main=32M', '-r', root, '-g', '800x600', *command],
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            try:
                window = until(lambda: call('xdotool', 'search', '--onlyvisible', '--name', '^inferno$', check=False).strip(), 'guest window missing').decode()

                def capture():
                    return Image.open(io.BytesIO(call('import', '-window', window, 'png:-'))).convert('RGB')

                def bounds():
                    image = capture()
                    delta = ImageChops.difference(image, Image.new('RGB', image.size, (232, 236, 241)))
                    r,g,b = delta.split()
                    return ImageChops.lighter(ImageChops.lighter(r,g),b).point(lambda v: 255 if v==0 else 0).getbbox()

                def key(*keys):
                    call('xdotool', 'key', '--clearmodifiers', '--delay', '100', *keys)
                    time.sleep(.25)

                def move(x, y):
                    return ('mousemove', '--window', window, str(x), str(y))

                def click(x, y):
                    call('xdotool', *move(x, y), 'sleep', '.04', 'mousedown', '1', 'sleep', '.16', 'mouseup', '1')
                    time.sleep(.25)

                def wheel(button):
                    left, top, _, _ = bounds()
                    call('xdotool', *move(left + 160, top + 135), 'sleep', '.25', 'click', str(button))

                def text(value):
                    call('xdotool', 'type', '--clearmodifiers', '--delay', '115', '--', value)
                    time.sleep(.35)

                def label(expected, region=None, mode='11', threshold=True):
                    area = capture().crop(region or bounds())
                    if threshold:
                        area = area.convert('L').point(lambda v: 255 if v > 145 else 0)
                    area = area.resize((area.width * 4, area.height * 4), Image.Resampling.BICUBIC)
                    png = io.BytesIO()
                    area.save(png, format='PNG')
                    result = subprocess.run(['tesseract', 'stdin', 'stdout', '--psm', mode],
                                            input=png.getvalue(), capture_output=True, timeout=5, check=True)
                    text = result.stdout.decode(errors='replace').casefold()
                    return ''.join(expected.casefold().split()) in ''.join(text.split())

                def first_row(expected):
                    box = bounds()
                    if box is None:
                        assert b'EXPLORER_EXIT' not in log_tail(), 'Explorer exited while browsing'
                        return False
                    left, top, _, _ = box
                    return label(expected, (left + 6, top + 100, left + 200, top + 125), '7')

                def first_row_image():
                    left, top, _, _ = bounds()
                    return capture().crop((left + 6, top + 100, left + 140, top + 125))

                def path_contains(expected):
                    box = bounds()
                    if box is None:
                        return False
                    left, top, right, _ = box
                    return label(expected, (left + 7, top + 36, right - 8, top + 66), '7', threshold=False)

                def toolbar(index):
                    left, top, right, _ = bounds()
                    cell = (right - left - 12) / 6
                    click(int(left + 6 + (index + .5) * cell), top + 16)

                def location(path):
                    key('ctrl+l')
                    key('ctrl+a')
                    text(path)
                    key('Return')

                def first_frame():
                    assert b'EXPLORER_EXIT' not in log_tail(), 'Explorer exited before its first frame'
                    return bounds()

                box = until(first_frame, 'Explorer did not paint', timeout=24)
                print('Explorer first frame', box, flush=True)

                call('xdotool', 'windowfocus', '--sync', window)
                until(lambda: first_row('targe'), 'fixture folder missing')
                initial_row = first_row_image()
                wheel(5)
                until(lambda: first_row('row-'), 'wheel down did not scroll the list')
                wheel(4)
                until(lambda: ImageChops.difference(initial_row, first_row_image()).getbbox() is None,
                      'wheel up did not restore the selected folder')
                until(lambda: label('1 selected', threshold=False), 'wheel changed the selection')
                print('Guest wheel down and up preserved selection', flush=True)
                toolbar(4)
                until(lambda: path_contains('target'), 'Open did not enter target')
                toolbar(0)
                until(lambda: first_row('targe'), 'Back did not return to fixture')
                toolbar(1)
                until(lambda: path_contains('target'), 'Forward did not enter target')
                toolbar(2)
                until(lambda: first_row('targe'), 'Up did not return to fixture')
                print('Guest Open, Back, Forward and Up passed', flush=True)
                left, top, _, _ = bounds()
                click(left + 60, top + 85)
                key('Home')
                until(lambda: label('zz-sample.txt', threshold=False), 'reverse name sort did not bring the last row to the top')
                click(left + 60, top + 85)
                key('End')
                until(lambda: label('zz-sample.txt', threshold=True), 'End did not scroll to final row')
                toolbar(4)
                until(lambda: label('guest preview content', threshold=False), 'Open did not preview selected UTF-8 text')
                key('Escape')
                key('ctrl+c')
                location('target')
                until(lambda: path_contains('target'), 'relative location did not enter target')
                key('ctrl+v')
                until(lambda: (fixture/'target/zz-sample.txt').is_file(), 'Paste did not copy the file')
                assert (fixture/'target/zz-sample.txt').read_text() == 'Explorer guest preview content\n'
                key('Home', 'Delete')
                until(lambda: label('Permanently delete'), 'delete confirmation missing')
                key('Escape')
                assert (fixture/'target/zz-sample.txt').exists()
                key('Delete', 'Return')
                until(lambda: not (fixture/'target/zz-sample.txt').exists(), 'confirmed Delete did not remove the copy')
                assert (fixture/'zz-sample.txt').exists()
                print('Guest selection, sorting, scrolling, preview, location, copy and delete passed', flush=True)
                key('ctrl+shift+n')
                text('created-folder')
                key('Return')
                until(lambda: (fixture/'target/created-folder').is_dir(), 'folder creation failed')
                toolbar(5)
                until(lambda: label('New file', threshold=False), 'Actions did not open')
                left, top, right, _ = bounds()
                click((left+right)//2, top+85)
                text('created-file')
                key('Return')
                until(lambda: (fixture/'target/created-file').is_file(), 'Actions did not create a file')
                (fixture/'target/externally-added').touch()
                toolbar(3)
                until(lambda: label('externally-added', threshold=False), 'Refresh did not show the added file')
                print('Guest file creation, folder creation and refresh passed', flush=True)

                def resize(dx, dy):
                    left, top, right, bottom = bounds()
                    call('xdotool', *move(right-3, bottom-3), 'mousedown', '1', 'sleep', '.16',
                         *move(right-3+dx,bottom-3+dy), 'sleep', '.16', 'mouseup', '1')
                    return until(lambda: (new := bounds()) and new[2]-new[0] == right-left+dx and
                                 new[3]-new[1] == bottom-top+dy and new, 'resize did not reflow the surface')

                print('Explorer grew to', resize(185, 105), flush=True)
                until(lambda: label('externally-added', threshold=False), 'content missing after resize')
                until(lambda: label('Modified', threshold=False), 'wider window did not reveal the Modified column')
                print('Explorer shrank to', resize(-171, -97), flush=True)
                until(lambda: not label('Modified', threshold=False), 'narrower window kept the wide column layout')
                for _ in range(24):
                    toolbar(0)
                    until(lambda: first_row('targe'), 'Back failed during repeated navigation')
                    toolbar(1)
                    until(lambda: label('externally-added', threshold=False), 'Forward failed during repeated navigation')
                left, top, right, _ = bounds()
                click(right-7, top-10)
                until(lambda: bounds() is None and b'0\nEXPLORER_EXIT' in log_tail(), 'close did not exit successfully')
                if memory_report:
                    until(lambda: any(line.endswith(b' main') for line in log_tail().splitlines()),
                          'guest allocator report missing')
                assert not log_contains(b'arena main too large'), 'Explorer exhausted the guest heap'
                print('Explorer first paint, navigation, scrolling, file actions, resize and close at 32 MiB passed', flush=True)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=3)
                print(log_tail().decode(errors='replace'), end='')


if __name__ == '__main__':
    main()
