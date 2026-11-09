#!/usr/bin/env python3
"""Native and saved-IR operation history, confined to owned fixture state."""
import os
from pathlib import Path
import resource
import shutil
import subprocess
from native_limits import allocation_probe

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'build/operation-history-fixture'


def command(*args, **kwargs):
    subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def main():
    assert subprocess.run(['git', 'check-ignore', str(FIXTURE)], cwd=ROOT,
                          stdout=subprocess.DEVNULL).returncode == 0
    source = 'tests/operation_history_test.zi'
    for args in (
        ['build', '--project', '--target=c', '--exe', '--entry', 'operation_history_test:main', '-o', 'build/operation-history-test-c', source],
        ['ir', '--project', '--entry', 'operation_history_test:main', '-o', 'build/operation-history-test-ir', source],
        ['build', '--project', '--target=c', '--exe', '--entry', 'operation_history_test:main', '-o', 'build/operation-history-test-saved-c', 'build/operation-history-test-ir/operation_history_test.zir'],
    ):
        command('build-queue', '--', './scripts/ziran.sh', *args)
    for output in ('operation-history-test-c', 'operation-history-test-saved-c'):
        binary = ROOT / 'build' / output / 'operation_history_test'
        for mode in ('regular', 'fds', 'oom', 'cross'):
            shutil.rmtree(FIXTURE, ignore_errors=True)
            FIXTURE.mkdir(mode=0o700)
            for name in ('home', 'data', 'config', 'runtime'):
                (FIXTURE / name).mkdir(mode=0o700)
            env = dict(os.environ, HOME=str(FIXTURE / 'home'), XDG_DATA_HOME=str(FIXTURE / 'data'),
                       XDG_CONFIG_HOME=str(FIXTURE / 'config'), XDG_RUNTIME_DIR=str(FIXTURE / 'runtime'))
            for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS'):
                env.pop(name, None)
            arguments = [str(binary), *([] if mode == 'regular' else ['--' + mode]), str(FIXTURE)]
            print(f'Local test {output}: {mode}', flush=True)
            if mode == 'cross':
                mount = FIXTURE / 'second-filesystem'; mount.mkdir(mode=0o700)
                command('unshare', '--user', '--map-root-user', '--mount', '--',
                        'sh', '-eu', '-c', 'mount -t tmpfs -o size=16m,mode=0700 tmpfs "$1"; exec "$2" --cross "$3" "$1"',
                        'history-test', str(mount), str(binary), str(FIXTURE), env=env, timeout=90)
            elif mode == 'oom':
                previous = dict(os.environ)
                try:
                    os.environ.clear(); os.environ.update(env)
                    result, ceiling = allocation_probe(arguments, FIXTURE / 'oom-ready', 12 * 1024 * 1024)
                finally:
                    os.environ.clear(); os.environ.update(previous)
                assert result.returncode == 0, (result.stdout[-2000:], result.stderr[-2000:])
                print(result.stdout.strip(), flush=True)
            else:
                def limits():
                    if mode == 'fds': resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
                command(*arguments, env=env, preexec_fn=limits, timeout=90)
            if mode == 'regular':
                metadata = list((FIXTURE / 'data/shelf/undo').glob('operation-*/original-path'))
                assert metadata and all(p.read_bytes().startswith(os.fsencode(FIXTURE)) for p in metadata)
                assert not list((FIXTURE / 'a').glob('.shelf-undo-*'))
                assert not list((FIXTURE / 'b').glob('.shelf-undo-*'))
    print('Operation history source/saved-IR local tests passed', flush=True)


if __name__ == '__main__': main()
