#!/usr/bin/env python3
"""Native and saved-IR operation history, confined to owned fixture state."""
import os
from pathlib import Path
import resource
import subprocess
from tempfile import TemporaryDirectory
from native_limits import allocation_probe

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'


def command(*args, **kwargs):
    subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def cross_device(binary, fixture, env):
    shared_memory = Path('/dev/shm')
    if shared_memory.is_dir() and shared_memory.stat().st_dev != fixture.stat().st_dev:
        with TemporaryDirectory(prefix='explorer-history-', dir=shared_memory) as second:
            command(str(binary), '--cross', str(fixture), second, env=env, timeout=90)
        return
    mount = fixture / 'second-filesystem'
    mount.mkdir(mode=0o700)
    command('unshare', '--user', '--map-root-user', '--mount', '--',
            'sh', '-eu', '-c', 'mount -t tmpfs -o size=16m,mode=0700 tmpfs "$1"; exec "$2" --cross "$3" "$1"',
            'history-test', str(mount), str(binary), str(fixture), env=env, timeout=90)


def main():
    BUILD.mkdir(exist_ok=True)
    source = 'tests/operation_history_test.zi'
    for args in (
        ['build', '--project', '--target=c', '--exe', '--entry', 'operation_history_test:main', '-o', 'build/operation-history-test-c', source],
        ['ir', '--project', '--entry', 'operation_history_test:main', '-o', 'build/operation-history-test-ir', source],
        ['build', '--project', '--target=c', '--exe', '--entry', 'operation_history_test:main', '-o', 'build/operation-history-test-saved-c', 'build/operation-history-test-ir/operation_history_test.zir'],
    ):
        command('./scripts/ziran.sh', *args)
    for output in ('operation-history-test-c', 'operation-history-test-saved-c'):
        binary = ROOT / 'build' / output / 'operation_history_test'
        for mode in ('regular', 'fds', 'oom', 'cross'):
            with TemporaryDirectory(prefix='operation-history-', dir=BUILD) as directory:
                fixture = Path(directory)
                for name in ('home', 'data', 'config', 'runtime'):
                    (fixture / name).mkdir(mode=0o700)
                env = dict(os.environ, HOME=str(fixture / 'home'), XDG_DATA_HOME=str(fixture / 'data'),
                           XDG_CONFIG_HOME=str(fixture / 'config'), XDG_RUNTIME_DIR=str(fixture / 'runtime'))
                for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS'):
                    env.pop(name, None)
                arguments = [str(binary), *([] if mode == 'regular' else ['--' + mode]), str(fixture)]
                print(f'Local test {output}: {mode}', flush=True)
                if mode == 'cross':
                    cross_device(binary, fixture, env)
                elif mode == 'oom':
                    previous = dict(os.environ)
                    try:
                        os.environ.clear(); os.environ.update(env)
                        result, ceiling = allocation_probe(arguments, fixture / 'oom-ready', 12 * 1024 * 1024)
                    finally:
                        os.environ.clear(); os.environ.update(previous)
                    assert result.returncode == 0, (result.stdout[-2000:], result.stderr[-2000:])
                    print(result.stdout.strip(), flush=True)
                else:
                    def limits():
                        if mode == 'fds': resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
                    command(*arguments, env=env, preexec_fn=limits, timeout=90)
                if mode == 'regular':
                    metadata = list((fixture / 'data/explorer/undo').glob('operation-*/original-path'))
                    assert metadata and all(p.read_bytes().startswith(os.fsencode(fixture)) for p in metadata)
                    assert not list((fixture / 'a').glob('.explorer-undo-*'))
                    assert not list((fixture / 'b').glob('.explorer-undo-*'))
    print('Operation history source/saved-IR local tests passed', flush=True)


if __name__ == '__main__': main()
