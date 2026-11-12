#!/usr/bin/env python3
"""Build and run actual source/saved-IR GIO tests in private XDG/DBus state."""
import datetime
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote_from_bytes
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]


def command(*args, **kwargs):
    subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def fixture():
    # private_desktop owns this entire XDG tree and removes it after this run.
    data = Path(os.environ["XDG_DATA_HOME"])
    root = data.parent / "locations-fixture"
    files = root / "files"
    files.mkdir(parents=True)
    (files / "folder").mkdir()
    (files / "note.txt").write_text("note", encoding="utf-8")
    (files / ".hidden").write_text("hidden", encoding="utf-8")
    (files / "space #%.txt").write_text("special", encoding="utf-8")
    (files / "link").symlink_to("note.txt")
    raw = os.fsencode(files) + b"/raw-\xff #%\n"
    descriptor = os.open(raw, os.O_CREAT | os.O_WRONLY, 0o600)
    os.write(descriptor, b"raw")
    os.close(descriptor)
    (root / "denied").mkdir(mode=0)
    busy = root / "busy"
    busy.mkdir()
    for index in range(2048):
        (busy / f"entry-{index}").touch()
    now = datetime.datetime.now(datetime.timezone.utc)

    def uri(path):
        return "file://" + quote_from_bytes(os.fsencode(path), safe="/")

    def item(address, title, seconds):
        stamp = (now - datetime.timedelta(seconds=seconds)).isoformat()
        return f'''<bookmark href="{escape(address, {'"': '&quot;'})}" added="{stamp}" modified="{stamp}" visited="{stamp}">
<title>{escape(title)}</title><info><metadata owner="http://freedesktop.org">
<mime:mime-type type="text/plain"/><bookmark:applications>
<bookmark:application name="Explorer test" exec="explorer %u" modified="{stamp}" count="1"/>
</bookmark:applications></metadata></info></bookmark>'''

    history = '''<?xml version="1.0" encoding="UTF-8"?>
<xbel version="1.0" xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks"
xmlns:mime="http://www.freedesktop.org/standards/shared-mime-info">'''
    history += item(uri(files / "note.txt"), "Recent note", 20)
    history += item(uri(raw), "Raw note", 10)
    history += item("sftp://example.invalid/remote.txt", "Remote note", 0)
    history += item(uri(files / "gone.txt"), "Vanished note", 30)
    history += item("file://remote.invalid/path", "Nonlocal file note", 40)
    history += "</xbel>"
    (data / "recently-used.xbel").write_text(history, encoding="utf-8")
    return root


def run(binary, local_only):
    root = fixture()
    os.environ["G_DEBUG"] = "fatal-criticals"
    if local_only:
        os.environ["GIO_USE_VFS"] = "local"
    # A fresh private bus deliberately starts without gio/Thunar pre-mounting
    # virtual roots. Explorer must activate the native backend itself.
    try:
        command("stdbuf", "-oL", str(binary), str(root), timeout=65)
    finally:
        (root / "denied").chmod(0o700)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        run(Path(sys.argv[2]), "--local-only" in sys.argv[3:])
        return
    ignored = subprocess.run(["git", "check-ignore", "build/desktop-locations-test-c"],
                             cwd=ROOT, capture_output=True, check=False)
    if ignored.returncode:
        raise RuntimeError("Native test outputs must be ignored")
    launcher = str(ROOT / "scripts/ziran.sh")
    entry = "desktop_locations_test:main"
    source = "tests/desktop_locations_test.zi"
    command("build-queue", "--", launcher, "build", "--project", "--target=c", "--exe",
            "--entry", entry, "-o", "build/desktop-locations-test-c", source)
    command("build-queue", "--", launcher, "ir", "--project", "--entry", entry,
            "-o", "build/desktop-locations-test-ir", source)
    command("build-queue", "--", launcher, "build", "--project", "--target=c", "--exe",
            "--entry", entry, "-o", "build/desktop-locations-test-saved-c",
            "build/desktop-locations-test-ir/desktop_locations_test.zir")
    for output in ("desktop-locations-test-c", "desktop-locations-test-saved-c"):
        binary = ROOT / "build" / output / "desktop_locations_test"
        for local_only in (False, True):
            print(f"Native test {output}, local-only={local_only}", flush=True)
            args = ["build-queue", "--", sys.executable, "tests/private_desktop.py", "--headless",
                    "dbus-run-session", "--", sys.executable, __file__, "--run", str(binary)]
            if local_only:
                args.append("--local-only")
            command(*args)


if __name__ == "__main__":
    main()
