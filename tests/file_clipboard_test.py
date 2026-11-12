#!/usr/bin/env python3
"""Private native Explorer/Thunar interchange, with a native GTK adversarial peer."""
import ctypes as C
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def gtk_peer():
    # Test fixture only: no application behavior lives in this GTK peer.
    gtk = C.CDLL('libgtk-3.so.0')
    gdk = C.CDLL('libgdk-3.so.0')
    gtk.gtk_init_check.argtypes = [C.c_void_p, C.c_void_p]
    assert gtk.gtk_init_check(None, None)
    gdk.gdk_atom_intern.argtypes = [C.c_char_p, C.c_int]
    gdk.gdk_atom_intern.restype = C.c_void_p
    atom = gdk.gdk_atom_intern(b'CLIPBOARD', 0)
    gtk.gtk_clipboard_get.argtypes = [C.c_void_p]
    gtk.gtk_clipboard_get.restype = C.c_void_p
    clipboard = gtk.gtk_clipboard_get(atom)
    mime = sys.argv[2].encode()
    if sys.argv[1] == '--read':
        gtk.gtk_clipboard_wait_for_contents.argtypes = [C.c_void_p, C.c_void_p]
        gtk.gtk_clipboard_wait_for_contents.restype = C.c_void_p
        data = gtk.gtk_clipboard_wait_for_contents(clipboard, gdk.gdk_atom_intern(mime, 0))
        assert data, 'missing MIME target'
        gtk.gtk_selection_data_get_length.argtypes = [C.c_void_p]
        gtk.gtk_selection_data_get_data.argtypes = [C.c_void_p]
        gtk.gtk_selection_data_get_data.restype = C.c_void_p
        size = gtk.gtk_selection_data_get_length(data)
        assert 0 <= size <= 2 * 1024 * 1024
        sys.stdout.buffer.write(C.string_at(gtk.gtk_selection_data_get_data(data), size))
        return
    payload = Path(sys.argv[3]).read_bytes()
    storage = C.create_string_buffer(payload)
    class Entry(C.Structure):
        _fields_ = [('target', C.c_char_p), ('flags', C.c_uint), ('info', C.c_uint)]
    get_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint, C.c_void_p)
    clear_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p)
    gtk.gtk_selection_data_get_target.argtypes = [C.c_void_p]
    gtk.gtk_selection_data_get_target.restype = C.c_void_p
    gtk.gtk_selection_data_set.argtypes = [C.c_void_p, C.c_void_p, C.c_int, C.c_void_p, C.c_int]
    @get_cb
    def get(_clipboard, selection, _info, _data):
        if sys.argv[1] == '--stall':
            time.sleep(3)
        gtk.gtk_selection_data_set(selection, gtk.gtk_selection_data_get_target(selection),
                                   8, storage, len(payload))
    @clear_cb
    def clear(_clipboard, _data):
        pass
    entries = (Entry * 1)(Entry(mime, 0, 0))
    gtk.gtk_clipboard_set_with_data.argtypes = [C.c_void_p, C.POINTER(Entry), C.c_uint,
                                               get_cb, clear_cb, C.c_void_p]
    assert gtk.gtk_clipboard_set_with_data(clipboard, entries, 1, get, clear, None)
    print('READY', flush=True)
    gtk.gtk_main()


def main():
    assert os.environ.get('DISPLAY') and os.environ.get('XDG_RUNTIME_DIR')
    repo = Path(__file__).resolve().parents[1]
    root = repo / 'build/file-clipboard-fixture'
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(mode=0o700)
    executable = Path(sys.argv[1]) if len(sys.argv) > 1 else repo / 'build/explorer-desktop'
    processes = []
    logs = []
    peer = None

    def run(*args):
        return subprocess.run(list(map(str, args)), check=True, capture_output=True,
                              text=True, timeout=10).stdout.strip()

    def wait(check, label):
        end = time.monotonic() + 12
        while time.monotonic() < end:
            if check():
                return
            time.sleep(.05)
        raise AssertionError(label)

    def start(command, name, cwd=root):
        log = (root / (name + '.log')).open('wb')
        logs.append(log)
        proc = subprocess.Popen(list(map(str, command)), cwd=cwd, stdout=log, stderr=log)
        processes.append(proc)
        windows = []
        def find():
            if proc.poll() is not None:
                raise AssertionError(f'{name} exited: {proc.returncode}')
            found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(proc.pid)],
                                   capture_output=True, text=True).stdout.splitlines()
            windows[:] = found
            return bool(found)
        wait(find, name + ' window')
        return windows[0]

    def key(window, *keys):
        run('xdotool', 'windowfocus', '--sync', window)
        for item in keys:
            run('xdotool', 'key', '--clearmodifiers', item)
            time.sleep(.15)

    def navigate(window, path):
        key(window, 'ctrl+l', 'ctrl+a')
        run('xdotool', 'type', '--clearmodifiers', '--delay', '1', path)
        key(window, 'Return')
        time.sleep(.4)

    def offer(mime, payload, stall=False):
        nonlocal peer
        payload_path = root / 'peer-payload'
        payload_path.write_bytes(payload)
        new = subprocess.Popen([sys.executable, __file__, '--stall' if stall else '--offer', mime, str(payload_path)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        processes.append(new)
        assert new.stdout.readline() == b'READY\n'
        if peer is not None:
            peer.terminate()
            peer.wait(timeout=5)
        peer = new

    try:
        explorer = start([executable], 'explorer')
        thunar = start(['thunar', root], 'thunar')
        special = 'é 世界 space\n%#?.txt'
        for index, (sender, receiver, cut) in enumerate(((explorer, thunar, False),
                (explorer, thunar, True), (thunar, explorer, False), (thunar, explorer, True))):
            source = root / f'source-{index}'
            target = root / f'target-{index}'
            source.mkdir(); target.mkdir()
            original = source / special
            original.write_text('native file clipboard\n')
            navigate(sender, source)
            key(sender, 'ctrl+a', 'ctrl+x' if cut else 'ctrl+c')
            expected = ('cut' if cut else 'copy').encode() + b'\n'
            advertised = subprocess.run([sys.executable, __file__, '--read',
                                        'x-special/gnome-copied-files'], capture_output=True,
                                       check=True, timeout=12).stdout
            assert advertised.startswith(expected), advertised
            assert b'%0A' in advertised.upper() and b'%25' in advertised
            navigate(receiver, target)
            key(receiver, 'ctrl+v')
            wait(lambda: (target / special).exists(), f'case {index} paste')
            assert (target / special).read_text() == 'native file clipboard\n'
            assert original.exists() != cut
            print(f'native case {index}: {"cut" if cut else "copy"} passed', flush=True)

        large = root / 'large-source'; large.mkdir()
        names = [f'file-{index:03}.txt' for index in range(300)]
        for name in names:
            (large / name).write_text(name)
        for cut in (False, True):
            target = root / ('large-cut' if cut else 'large-copy'); target.mkdir()
            navigate(explorer, large); key(explorer, 'ctrl+a', 'ctrl+x' if cut else 'ctrl+c')
            advertised = subprocess.run([sys.executable, __file__, '--read',
                                        'x-special/gnome-copied-files'], capture_output=True,
                                       check=True, timeout=12).stdout
            assert len(advertised.splitlines()) == 301, 'truncated native selection'
            navigate(thunar, target); key(thunar, 'ctrl+v')
            wait(lambda: len(list(target.iterdir())) == 300, '300-file native paste')
            assert all((target / name).read_text() == name for name in names)
            assert len(list(large.iterdir())) == (0 if cut else 300)
        print('native 300-file complete copy/cut selections passed', flush=True)

        offer('UTF8_STRING', b'publication must preserve this owner')
        for probe in (repo / 'build/file-clipboard-probe',
                      repo / 'build/file-clipboard-probe-saved-c/file_clipboard_probe'):
            subprocess.run([str(probe)], check=True, timeout=10)
        preserved = subprocess.run([sys.executable, __file__, '--read', 'UTF8_STRING'],
                                   capture_output=True, check=True, timeout=12).stdout
        assert preserved == b'publication must preserve this owner'
        offer('text/uri-list', b'cut\nfile:///prior\n')
        for probe in (repo / 'build/file-clipboard-probe',
                      repo / 'build/file-clipboard-probe-saved-c/file_clipboard_probe'):
            subprocess.run([str(probe), 'mime-change'], check=True, timeout=10)

        # Keep an old internal CUT selection, then replace the desktop owner.
        old = root / 'old-internal'; old.mkdir()
        original = old / 'keep.txt'; original.write_text('keep')
        target = root / 'invalid-target'; target.mkdir()
        navigate(explorer, old); key(explorer, 'ctrl+a', 'ctrl+x'); navigate(explorer, target)
        valid = original.as_uri().encode()
        invalid = [b'', b'cut\n', b'cut\nfile://', b'cut\nfile://remote/a',
                   b'cut\n' + valid + b'\nfile:///bad%GG', b'cut\nfile:///bad%00',
                   b'cut\nfile:///bad%FF', b'cut\nfile:///' + b'a' * 4096,
                   b'copy\n' + b'x' * 1048576]
        for payload in invalid:
            offer('x-special/gnome-copied-files', payload)
            key(explorer, 'ctrl+v')
            assert original.exists() and not list(target.iterdir()), payload[:100]
        offer('x-special/gnome-copied-files', b'cut\n' + valid + b'\n', stall=True)
        key(explorer, 'ctrl+v')
        time.sleep(1.3)
        assert original.exists() and not list(target.iterdir()), 'transport timeout mutated files'
        offer('UTF8_STRING', b'ordinary text replacing stale cut')
        key(explorer, 'ctrl+v')
        assert original.exists() and not list(target.iterdir())
        # URI-only lists copy; a failed operation retains a pending cut and error.
        offer('text/uri-list', b'# native URI peer\r\n' + valid + b'\r\n')
        key(explorer, 'ctrl+v')
        wait(lambda: (target / 'keep.txt').exists(), 'URI-only copy')
        assert original.exists()
        offer('x-special/gnome-copied-files', b'cut\nfile:///missing-explorer-clipboard-test\n')
        before = sorted(p.name for p in target.iterdir())
        key(explorer, 'ctrl+v')
        assert before == sorted(p.name for p in target.iterdir()) and original.exists()
        # Foreign cut consumption is cached: repeat paste cannot move it twice.
        offer('x-special/gnome-copied-files', b'cut\n' + valid + b'\n')
        key(explorer, 'ctrl+v')
        wait(lambda: not original.exists(), 'foreign cut')
        before = sorted(p.name for p in target.iterdir())
        key(explorer, 'ctrl+v')
        assert before == sorted(p.name for p in target.iterdir())
        # Retry only the pending suffix after a partially completed foreign cut.
        first = old / 'first.txt'; first.write_text('first')
        second = old / 'second.txt'
        offer('x-special/gnome-copied-files', b'cut\n' + first.as_uri().encode() +
              b'\n' + second.as_uri().encode() + b'\n')
        key(explorer, 'ctrl+v')
        wait(lambda: not first.exists(), 'partial cut completed prefix')
        assert (target / 'first.txt').read_text() == 'first'
        second.write_text('retry')
        key(explorer, 'ctrl+v')
        wait(lambda: not second.exists(), 'partial cut retry suffix')
        assert (target / 'second.txt').read_text() == 'retry'
        assert not (target / 'first (2).txt').exists()
        print('native malformed/remote/oversize/timeout/ownership/failure/consumed-cut/partial-retry local tests passed')
    finally:
        for proc in reversed(processes):
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=10)
        for log in logs:
            log.close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('--offer', '--read', '--stall'):
        gtk_peer()
    else:
        main()
