#!/usr/bin/env python3
"""Run Explorer's shared model in an owned Taiji guest at its default heap."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
from tempfile import TemporaryDirectory

from private_desktop import taiji_staging


def main():
    assert os.environ.get('EXPLORER_PRIVATE_DESKTOP') == '1'
    assert os.environ.get('HARMONY_DESKTOP_RECOVERY') == '0'
    root = Path(os.environ.get('TAIJIOS_ROOT', '../../taijiosnet/taijios')).resolve()
    emulator = Path(os.environ.get('TAIJIOS_EMULATOR', root / 'emu/Linux/o.emu'))
    staging = taiji_staging(root)
    with TemporaryDirectory(dir=staging, prefix='explorer-private-test-') as directory:
        fixture = Path(directory)
        guest = '/' + fixture.relative_to(root).as_posix()
        shutil.copyfile('build/taiji-model-test.zx', fixture / 'model.zx')
        (fixture / 'target').mkdir()
        (fixture / 'sample.txt').write_text('Explorer guest preview content\n')
        (fixture / '世界.txt').touch()
        (fixture / 'literal\\name.txt').touch()
        for i in range(80):
            (fixture / f'row-{i:02d}.txt').touch()
        large = fixture / 'large'
        large.mkdir()
        oversized = fixture / 'oversized'
        oversized.mkdir()
        for index in range(4097):
            name = f'entry-{index:04}.txt'
            (oversized / name).touch()
            if index < 1024:
                (large / name).touch()
        with (fixture / 'test.log').open('w+b') as output:
            process = subprocess.Popen([emulator, '-p', 'main=32M', '-r', root,
                                        '/dis/sh.dis', '-c', f'home={guest}; zxrun {guest}/model.zx; echo EXPLORER_GUEST_END $status'],
                                       stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                       start_new_session=True)
            try:
                process.wait(timeout=45)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
            output.seek(0)
            result = output.read(8192).decode(errors='replace')
        print(result, end='')
        assert 'Explorer Taiji model local tests passed\n0\nEXPLORER_GUEST_END' in result, process.returncode
        assert (fixture / 'target/new-folder').is_dir()
        assert (fixture / 'target/new-file').stat().st_size == 0
        assert not (fixture / 'target/sample.txt').exists()


if __name__ == '__main__':
    main()
