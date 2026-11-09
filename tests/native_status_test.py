#!/usr/bin/env python3
"""Compare footer policy with the installed Thunar on a private desktop."""
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def oracle(directory, selection, output, env):
    """Read actual GtkStatusbar labels, without reproducing Thunar formatting."""
    script = output.with_suffix(".gdb.py")
    script.write_text('''import gdb, json
inferior=gdb.selected_inferior()
def call(expr): return int(gdb.parse_and_eval(expr))
def ptr(address): return int.from_bytes(inferior.read_memory(address,8).tobytes(),'little')
texts=[]
def walk(widget, status=False):
    kind=gdb.parse_and_eval('(char*)g_type_name_from_instance((void*)%d)'%widget).string()
    status=status or kind.endswith('Statusbar')
    if status and kind=='GtkLabel':
        texts.append(gdb.parse_and_eval('(char*)gtk_label_get_text((void*)%d)'%widget).string())
    if call('(int)g_type_check_instance_is_a((void*)%d,(unsigned long)gtk_container_get_type())'%widget):
        first=node=call('(void*)gtk_container_get_children((void*)%d)'%widget)
        while node:
            walk(ptr(node),status); node=ptr(node+8)
        if first: call('(int)g_list_free((void*)%d)'%first)
first=node=call('(void*)gtk_window_list_toplevels()')
while node:
    walk(ptr(node)); node=ptr(node+8)
if first: call('(int)g_list_free((void*)%d)'%first)
open(OUTPUT,'w').write(json.dumps(texts))
'''.replace("OUTPUT", repr(str(output))))
    with output.with_suffix(".gdb.log").open("wb") as log:
        debugger = subprocess.Popen(["gdb", "-q", "-batch", "-ex", "set pagination off",
                                    "-ex", "set confirm off", "-ex", "run", "-ex",
                                    "source " + str(script), "-ex", "kill", "--args",
                                    "/usr/bin/thunar", str(directory)], env=env,
                                   stdout=log, stderr=log, start_new_session=True)
        try:
            child = None
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                assert debugger.poll() is None, f"Thunar debugger exited: {log.name}"
                children = Path(f"/proc/{debugger.pid}/task/{debugger.pid}/children").read_text().split()
                for candidate in children:
                    if Path(f"/proc/{candidate}/comm").read_text().strip() == "thunar":
                        child = int(candidate)
                if child:
                    result = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(child)],
                                            capture_output=True, text=True, env=env)
                    if result.returncode == 0:
                        window = result.stdout.splitlines()[0]
                        break
                time.sleep(.1)
            else:
                raise AssertionError("Private Thunar window missing")
            run("xdotool", "windowfocus", "--sync", window, env=env)
            time.sleep(.4)
            if selection:
                run("xdotool", "key", "--clearmodifiers", "ctrl+a" if selection == "all" else "Home", env=env)
            time.sleep(.7)
            os.kill(child, signal.SIGSTOP)
            assert debugger.wait(timeout=15) == 0, log.name
        finally:
            if debugger.poll() is None:
                os.killpg(debugger.pid, signal.SIGTERM)
                debugger.wait(timeout=5)
    labels = [text for text in json.loads(output.read_text()) if text]
    assert len(labels) == 1, labels
    return labels[0]


def main():
    assert os.environ.get("YUE_DESKTOP_RECOVERY") == "0"
    assert os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")
    root = Path(os.environ["XDG_DATA_HOME"]).parent / "native-status"
    root.mkdir()
    env = os.environ.copy()
    env.update(LC_ALL="C.UTF-8", LANGUAGE="")
    targets = root / "targets"
    targets.mkdir()
    (targets / "file.txt").write_bytes(b"x" * 1234)
    (targets / "folder").mkdir()
    cases = []
    for name, selection in (("empty", ""), ("mixed", ""), ("mixed", "all"),
                            ("folder", "one"), ("file", "one"), ("link", "one"),
                            ("folder-link", "one"), ("broken", "one"), ("unicode", "one"), ("image", "one")):
        directory = root / name
        if not directory.exists():
            directory.mkdir()
            if name == "mixed":
                (directory / "folder").mkdir()
                (directory / "note.txt").write_bytes(b"x" * 1234)
                (directory / ".hidden").write_bytes(b"hidden")
            elif name == "folder":
                (directory / "folder").mkdir()
            elif name == "file":
                (directory / "note.txt").write_bytes(b"x" * 1234)
            elif name == "link":
                (directory / "link").symlink_to(targets / "file.txt")
            elif name == "folder-link":
                (directory / "folder-link").symlink_to(targets / "folder")
            elif name == "broken":
                (directory / "broken").symlink_to("missing")
            elif name == "unicode":
                (directory / 'é "quoted".txt').write_bytes(b"text")
            elif name == "image":
                def chunk(kind, payload):
                    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
                (directory / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" +
                    chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)) +
                    chunk(b"IDAT", zlib.compress(b"\x00\x20\x40\x60\xff")) + chunk(b"IEND", b""))
        selected = sorted(path.name for path in directory.iterdir() if not path.name.startswith(".")) if selection else []
        expected = oracle(directory, selection, root / f"{name}-{selection or 'none'}.json", env)
        # Free space changes while independent applications run; selection never
        # includes it. Compare the complete stable part, then test free text below.
        if not selection:
            expected = expected.split("  |  Free space: ", 1)[0]
        for executable in sys.argv[1:]:
            actual = subprocess.check_output([executable, str(directory), "none", *selected], env=env, text=True).rstrip("\n")
            assert actual == expected, (name, selection, executable, actual, expected)
        cases.append({"directory": name, "selection": selection, "text": expected})

    # Native gettext plural catalogs and GLib's long IEC format for large files.
    libc = ctypes.CDLL(None)
    glib = ctypes.CDLL("libglib-2.0.so.0")
    libc.setlocale.argtypes = [ctypes.c_int, ctypes.c_char_p]
    libc.dngettext.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong]
    libc.dngettext.restype = ctypes.c_char_p
    libc.dgettext.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    libc.dgettext.restype = ctypes.c_char_p
    glib.g_format_size_full.argtypes = [ctypes.c_uint64, ctypes.c_int]
    glib.g_format_size_full.restype = ctypes.c_void_p
    glib.g_free.argtypes = [ctypes.c_void_p]
    glib.g_strdup_printf.restype = ctypes.c_void_p
    glib.g_strdup_printf.argtypes = [ctypes.c_char_p]

    def owned(pointer):
        assert pointer
        try:
            return ctypes.string_at(pointer)
        finally:
            glib.g_free(pointer)

    def translated(message):
        return libc.dgettext(b"thunar", message)

    def formatted(message, *args):
        return owned(glib.g_strdup_printf(translated(message), *(ctypes.c_char_p(arg) for arg in args)))

    locales = subprocess.check_output(["locale", "-a"], text=True).splitlines()
    message_locale = next((name for name in locales if name.lower() not in ("c", "posix", "c.utf8", "c.utf-8") and
                           ("utf8" in name.lower() or "utf-8" in name.lower())), None)
    assert message_locale, "Translation test requires an installed non-C UTF-8 locale"
    for language in ("de", "fr", "es", "ru", "ja", "zh_CN"):
        localized = dict(env, LANGUAGE=language, LC_ALL=message_locale)
        os.environ["LANGUAGE"] = language
        libc.setlocale(6, b"C")
        assert libc.setlocale(6, message_locale.encode())
        assert translated(b"Free space: %s") != b"Free space: %s", (language, "catalog not translated")
        folder = owned(glib.g_strdup_printf(libc.dngettext(b"thunar", b"%d folder", b"%d folders", 1), ctypes.c_int(1)))
        files = owned(glib.g_strdup_printf(libc.dngettext(b"thunar", b"%d file", b"%d files", 2), ctypes.c_int(2)))
        expected = b"  |  ".join((folder, formatted(b"%s: %s", files, owned(glib.g_format_size_full(1240, 3))),
                                   formatted(b"Free space: %s", owned(glib.g_format_size_full(4096, 2))))).decode()
        for executable in sys.argv[1:]:
            actual = subprocess.check_output([executable, str(root / "mixed"), "free"], env=localized, text=True).rstrip("\n")
            assert actual == expected, (language, actual, expected)
    for executable in sys.argv[1:]:
        # URI listings already carry GIO content types; a missing local path
        # must still use that description and must not stat a remote URI.
        actual = subprocess.check_output([executable, "network:///", "uri", "Network folder"], env=env, text=True).strip()
        assert actual == '"Network folder"  |  Folder', actual
        cache_root = root / ("cache-" + Path(executable).parent.name)
        actual = subprocess.check_output([executable, str(cache_root), "cache"], env=env, text=True).splitlines()
        assert actual == ["1 file: 1 byte", "2 files: 7 bytes", "2 files: 7 bytes", "2 files: 12 bytes", "2 files: 20 bytes"], actual
    (ROOT / "build/native-status-report.json").write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n")
    print(f"Native status: {len(cases)} actual Thunar states, URI fallback, cache invalidation, source/saved executables, six installed translation catalogs")


if __name__ == "__main__":
    main()
