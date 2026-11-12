#!/usr/bin/env python3
"""GTK bookmark compatibility and Explorer UI persistence on a private desktop."""
import argparse
import ctypes as C
import json
import os
import select
from pathlib import Path
import shutil
import subprocess
import sys
import time
from ui_test import menu_action, native_sidebar_geometry
from urllib.parse import quote_from_bytes


def gtk_bookmarks():
    gtk = C.CDLL('libgtk-3.so.0')
    gio = C.CDLL('libgio-2.0.so.0')
    glib = C.CDLL('libglib-2.0.so.0')
    obj = C.CDLL('libgobject-2.0.so.0')
    gtk.gtk_init_check.argtypes = [C.c_void_p, C.c_void_p]
    assert gtk.gtk_init_check(None, None)
    gtk.gtk_places_sidebar_new.restype = C.c_void_p
    sidebar = gtk.gtk_places_sidebar_new()
    assert sidebar
    gtk.gtk_widget_show.argtypes = [C.c_void_p]
    gtk.gtk_widget_show(sidebar)
    gtk.gtk_main_iteration_do.argtypes = [C.c_int]
    deadline = time.monotonic() + .5
    while time.monotonic() < deadline:
        while gtk.gtk_events_pending():
            gtk.gtk_main_iteration_do(False)
        time.sleep(.01)
    gtk.gtk_places_sidebar_get_nth_bookmark.argtypes = [C.c_void_p, C.c_int]
    gtk.gtk_places_sidebar_get_nth_bookmark.restype = C.c_void_p
    gio.g_file_get_uri.argtypes = [C.c_void_p]
    gio.g_file_get_uri.restype = C.c_void_p
    glib.g_free.argtypes = [C.c_void_p]
    obj.g_object_unref.argtypes = [C.c_void_p]
    uris = []
    for index in range(128):
        file = gtk.gtk_places_sidebar_get_nth_bookmark(sidebar, index)
        if not file:
            break
        uri = gio.g_file_get_uri(file)
        uris.append(C.string_at(uri).decode('utf-8'))
        glib.g_free(uri)
        obj.g_object_unref(file)
    gtk.gtk_widget_destroy.argtypes = [C.c_void_p]
    gtk.gtk_widget_destroy(sidebar)
    print(json.dumps(uris))


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path, default=repo / 'build/explorer-desktop')
    parser.add_argument('--gtk-only', action='store_true')
    options = parser.parse_args()
    assert os.environ.get('DISPLAY') and os.environ.get('XDG_RUNTIME_DIR')
    root = repo / 'build/bookmarks-ui-fixture'
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(mode=0o700)
    alpha = root / 'alpha space'; alpha.mkdir()
    beta = root / 'beta-é'; beta.mkdir()
    (alpha / 'proof.txt').write_text('alpha')
    (beta / 'proof.txt').write_text('beta')
    uri = lambda p: 'file://' + quote_from_bytes(os.fsencode(p), safe='/')
    path = Path(os.environ['XDG_CONFIG_HOME']) / 'gtk-3.0/bookmarks'
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    unknown = b'sftp://host/remote Remote\nfile:///broken%GG malformed\n# unknown record\n\xff unknown raw text\n'
    path.write_bytes(unknown + (uri(alpha) + ' Initial\talpha\n').encode())
    def native_uris():
        run = subprocess.run([sys.executable, __file__, '--gtk'], check=True,
                             capture_output=True, text=True, timeout=15)
        return json.loads(run.stdout)
    loaded = native_uris()
    assert uri(alpha) in loaded, f'installed GTK bookmark binding did not read standard fixture: {loaded!r}'
    print('installed GTK3 bookmark format and public sidebar binding passed', flush=True)
    if options.gtk_only:
        return
    captured = root / 'opened-path'
    env = os.environ.copy(); env['KRYON_TEST_OPEN_URI_CAPTURE'] = str(captured)
    process = None
    peer = None
    log = (root / 'app.log').open('wb')
    try:
        def healthy():
            assert process.poll() is None, f'Explorer exited {process.returncode}; see {root / "app.log"}'
        def xdo(*args):
            healthy()
            return subprocess.run(['xdotool', *map(str, args)], check=True,
                                  capture_output=True, text=True, timeout=10).stdout.strip()
        def start():
            nonlocal process
            process = subprocess.Popen([str(options.executable)], cwd=root, env=env,
                                       stdout=log, stderr=log)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(process.pid)],
                                       capture_output=True, text=True)
                if found.returncode == 0:
                    window = found.stdout.splitlines()[0]
                    xdo('windowfocus', '--sync', window)
                    time.sleep(1.0)
                    return window
                healthy(); time.sleep(.05)
            raise AssertionError('missing owned Explorer window')
        window = start()
        native_geometry = native_sidebar_geometry()
        (root / 'native-sidebar-geometry.json').write_text(json.dumps(native_geometry, indent=2) + '\n')
        first_bookmark, second_bookmark = native_geometry['bookmark_centers']
        def key(*keys):
            for item in keys:
                xdo('key', '--clearmodifiers', item); time.sleep(.15); healthy()
        def click(x, y):
            xdo('mousemove', '--window', window, x, y); xdo('click', '1')
            time.sleep(.3); healthy()
        def paste(value):
            nonlocal peer
            payload = root / 'editor-payload'
            payload.write_text(str(value))
            peer = subprocess.Popen([sys.executable, str(repo / 'tests/file_clipboard_test.py'),
                                     '--offer', 'UTF8_STRING', str(payload)],
                                    stdout=subprocess.PIPE, stderr=log)
            try:
                assert select.select([peer.stdout], [], [], 10)[0], 'native text peer did not become ready'
                assert peer.stdout.readline().strip() == b'READY'
                key('ctrl+v')
                time.sleep(.2)
            finally:
                peer.terminate(); peer.wait(timeout=10); peer.stdout.close(); peer = None
        def navigate(folder):
            key('ctrl+l', 'ctrl+a')
            paste(folder)
            key('Return')
        def check_file(local_order, label=None):
            contents = path.read_bytes()
            assert contents.startswith(unknown), 'unsupported records changed'
            lines = contents.decode('utf-8', 'surrogateescape').splitlines()
            local = [line.split(' ', 1)[0] for line in lines if line.startswith('file://') and '%GG' not in line]
            assert local == [uri(p) for p in local_order], local
            if label is not None:
                assert (uri(beta) + ' ' + label) in lines
        def opened(folder):
            key('ctrl+2', 'Home', 'Return')
            assert captured.read_bytes() == os.fsencode(folder / 'proof.txt')
        navigate(beta)
        opened(beta)  # Assert navigation before publishing the current folder.
        key('ctrl+d')  # A selected file is never bookmarked as its parent.
        check_file([alpha])
        key('Escape')  # With no selection, Add bookmarks the current folder.
        menu_action(xdo, window, "Bookmarks", 0)  # Add current.
        check_file([alpha, beta])
        navigate(root)
        key('ctrl+s'); paste(beta.name); key('Return', 'ctrl+d')
        check_file([alpha, beta])  # The selected directory, never root, is added.
        navigate(beta); key('Escape', 'ctrl+d')
        menu_action(xdo, window, "Bookmarks", 1)  # Rename the selected new bookmark.
        key('ctrl+a'); paste('Favorite é')
        key('Return'); check_file([alpha, beta], 'Favorite é')
        menu_action(xdo, window, "Bookmarks", 3); check_file([beta, alpha], 'Favorite é')
        menu_action(xdo, window, "Bookmarks", 4); check_file([alpha, beta], 'Favorite é')
        menu_action(xdo, window, "Bookmarks", 3); check_file([beta, alpha], 'Favorite é')
        navigate(root)
        click(75, first_bookmark)  # Activate even though this bookmark is already selected.
        opened(beta)
        assert uri(beta) in native_uris(), 'installed GTK did not read Explorer-added bookmark'
        process.terminate(); process.wait(timeout=10)
        window = start()
        click(75, first_bookmark); opened(beta)
        menu_action(xdo, window, "Bookmarks", 2); check_file([alpha])  # Remove, then restart.
        process.terminate(); process.wait(timeout=10)
        window = start()
        click(75, first_bookmark); opened(alpha)
        # Native external edits refresh without restarting Explorer.
        path.write_bytes(unknown + (uri(beta) + ' External beta\n').encode())
        time.sleep(1.3)
        click(75, first_bookmark); opened(beta)
        check_file([beta], 'External beta')
        # GTK file URIs can represent raw Unix filename bytes. Explorer keeps those
        # identities and uses safe captions, independently of clipboard policy.
        raw = os.fsencode(root) + b'/raw-\xff'
        os.mkdir(raw)
        with open(raw + b'/proof.txt', 'wb') as stream:
            stream.write(b'raw')
        raw_uri = 'file://' + quote_from_bytes(raw, safe='/')
        path.write_bytes(path.read_bytes() + (raw_uri + '\n').encode())
        time.sleep(1.3)
        click(75, second_bookmark)
        key('ctrl+2', 'Home', 'Return')
        assert captured.read_bytes() == raw + b'/proof.txt'
        assert raw_uri in native_uris()
        original = path.read_bytes()
        target = path.with_name('bookmarks-target')
        path.rename(target)
        path.symlink_to(target.name)
        time.sleep(1.3)
        menu_action(xdo, window, "Bookmarks", 1)
        key('ctrl+a'); paste('Do not replace symlink'); key('Return')
        assert path.is_symlink() and target.read_bytes() == original
        key('Escape')
        print('Explorer bookmark add/rename/reorder/reselect/remove/restart/external refresh/raw-name/symlink GUI tests passed', flush=True)
    except Exception:
        if process and process.poll() is None:
            subprocess.run(['import', '-window', window, str(root / 'failure.png')],
                           capture_output=True, timeout=10)
        raise
    finally:
        if peer and peer.poll() is None:
            peer.terminate(); peer.wait(timeout=10)
        if process and process.poll() is None:
            process.terminate()
        if process:
            process.wait(timeout=10)
        log.close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--gtk':
        gtk_bookmarks()
    else:
        main()
