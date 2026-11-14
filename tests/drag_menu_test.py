#!/usr/bin/env python3
"""Drag files out of Explorer and use its Thunar context menus, on a private Xvfb.

Run through tests/private_desktop.py (make test-drag-menu). Every window,
pointer and drop happens on the test's own display: Explorer drags a file onto
an independent python-xlib XDND target, into a real Thunar window and, when
Chromium is installed, onto a web page's drop zone; it also drops onto one of
its own folders, and right-click menus perform Thunar's actions.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from ui_test import require_private_display, native_chrome_geometry

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "build/drag-menu"
PROBE = REPO / "build/context-menu-probe-c/context_menu_probe"


def xdo(*args):
    return subprocess.check_output(["xdotool", *map(str, args)], text=True, timeout=10).strip()


def capture(name):
    path = OUTPUT / f"{name}.png"
    subprocess.run(["import", "-window", "root", str(path)], check=True, timeout=15)
    return path


def wait(check, reason, process=None, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return
        if process is not None:
            assert process.poll() is None, "Explorer exited: " + reason
        time.sleep(.05)
    raise AssertionError(reason)


def drag(start, end, steps=24, hold=.4, snapshot=None):
    xdo("mousemove", "--sync", *start)
    time.sleep(.15)
    xdo("mousedown", 1)
    time.sleep(.15)
    for step in range(1, steps + 1):
        xdo("mousemove", "--sync", start[0] + (end[0] - start[0]) * step // steps,
            start[1] + (end[1] - start[1]) * step // steps)
        time.sleep(.03)
    time.sleep(hold)
    if snapshot:
        capture(snapshot)
    xdo("mouseup", 1)
    time.sleep(.6)


def menu_labels(arguments):
    output = subprocess.run([str(PROBE), *arguments], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(output.stdout)


def downs_to(entries, label):
    """Down presses from a fresh menu to an entry, skipping separators and
    disabled rows as GTK keyboard navigation does."""
    count = 0
    for entry in entries:
        if entry.get("separator") or not entry["sensitive"]:
            continue
        count += 1
        if entry["label"] == label:
            return count
    raise AssertionError(f"{label!r} not in menu {[e.get('label') for e in entries]}")


def main():
    require_private_display()
    assert os.environ.get("EXPLORER_PRIVATE_DESKTOP") == "1"
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    home = Path(os.environ["HOME"])
    fixture = home / "drag-fixture"
    fixture.mkdir()
    (fixture / "Inbox").mkdir()
    (fixture / "Target").mkdir()
    (fixture / "a drag me.txt").write_text("drag out\n")
    (fixture / "b move me.txt").write_text("move inside\n")
    (fixture / "c click me.txt").write_text("plain click\n")
    (fixture / "d menu me.txt").write_text("context menu\n")
    thunar_folder = home / "thunar-target"
    thunar_folder.mkdir()
    report = {"captures": []}
    geometry = native_chrome_geometry()
    left = 170 + geometry["separator_width"]
    top = geometry["menu_height"] + geometry["toolbar_height"] + geometry["frame_top"] + geometry["header_height"]
    row = geometry["row_height"]
    log = (OUTPUT / "explorer.log").open("wb")
    process = subprocess.Popen([str(REPO / "build/explorer-desktop")], cwd=fixture, stdout=log, stderr=subprocess.STDOUT)
    helpers = []
    try:
        found = []

        def locate():
            result = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(process.pid)],
                                    capture_output=True, text=True)
            found[:] = result.stdout.splitlines()
            return bool(found)
        wait(locate, "Explorer window missing", process)
        window = found[0]
        xdo("windowmove", "--sync", window, 0, 0)
        xdo("windowsize", "--sync", window, 1000, 700)
        xdo("windowfocus", "--sync", window)
        time.sleep(.6)

        def key(*keys):
            for item in keys:
                xdo("key", "--clearmodifiers", "--window", window, item)
                time.sleep(.12)
        key("ctrl+l", "ctrl+a")
        xdo("type", "--clearmodifiers", "--delay", "2", str(fixture))
        key("Return")
        time.sleep(.4)
        key("ctrl+2")
        time.sleep(.4)
        # Folders first, then names: Inbox, Target, a, b, c, d.
        def row_center(index):
            return (left + 140, top + index * row + row // 2)
        report["captures"].append(str(capture("01-list")))

        # A plain click still selects exactly one file: Delete trashes only it.
        xdo("mousemove", "--sync", *row_center(4)); xdo("click", 1); time.sleep(.3)
        key("Delete")
        wait(lambda: not (fixture / "c click me.txt").exists(), "plain click did not select the file", process)
        assert (fixture / "d menu me.txt").exists() and (fixture / "a drag me.txt").exists()
        key("ctrl+z")
        wait(lambda: (fixture / "c click me.txt").exists(), "undo of the trash failed", process)
        time.sleep(.3)

        # Drag out to an independent XDND target.
        target_json = OUTPUT / "xdnd-target.json"
        target = subprocess.Popen([sys.executable, str(REPO / "tests/xdnd_target.py"), "1150", "150", "300", "260",
                                   str(target_json)], stdout=subprocess.PIPE, text=True)
        helpers.append(target)
        assert target.stdout.readline().strip() == "ready"
        drag(row_center(2), (1300, 280))
        target.wait(timeout=20)
        received = json.loads(target_json.read_text())
        expected = (fixture / "a drag me.txt").as_uri() + "\r\n"
        assert received["data"] == expected, received
        assert received["types"][:1] == ["text/uri-list"], received
        assert {"text/plain;charset=utf-8", "UTF8_STRING", "text/plain"} <= set(received["targets"]), received
        assert received["drops"] == 1 and set(received["actions"]) == {"XdndActionCopy"}, received
        assert (fixture / "a drag me.txt").exists(), "a copy drop must leave the source"
        report["xdnd_target"] = received

        # Drag into a real Thunar window: Thunar receives the URI and, on the
        # same filesystem, moves the file as it does for its own drags.
        thunar_env = dict(os.environ); thunar_env.pop("NO_AT_BRIDGE", None)
        thunar = subprocess.Popen(["thunar", str(thunar_folder)], env=thunar_env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        helpers.append(thunar)
        thunar_window = []

        def locate_thunar():
            result = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(thunar.pid)],
                                    capture_output=True, text=True)
            thunar_window[:] = result.stdout.splitlines()
            return bool(thunar_window)
        wait(locate_thunar, "Thunar window missing", timeout=20)
        xdo("windowmove", "--sync", thunar_window[0], 1010, 450)
        xdo("windowsize", "--sync", thunar_window[0], 560, 420)
        time.sleep(1.5)
        xdo("windowfocus", "--sync", window); time.sleep(.3)
        drag(row_center(2), (1350, 700), hold=1.2, snapshot="02-thunar-hover")
        wait(lambda: (thunar_folder / "a drag me.txt").exists(), "Thunar did not receive the dropped file", timeout=15)
        report["thunar"] = {"received": True, "source_kept": (fixture / "a drag me.txt").exists()}
        report["captures"].append(str(capture("02-after-thunar-drop")))
        thunar.terminate(); thunar.wait(timeout=10)
        xdo("windowfocus", "--sync", window); time.sleep(.3)
        key("F5"); time.sleep(.4)
        # After a move the list is Inbox, Target, b, c, d; refresh row centers.
        names = sorted(p.name for p in fixture.iterdir() if p.is_dir()) + sorted(p.name for p in fixture.iterdir() if p.is_file())

        def row_of(name):
            return row_center(names.index(name))

        # Drop onto one of Explorer's own folders: Thunar's same-filesystem move.
        drag(row_of("b move me.txt"), row_of("Target"))
        wait(lambda: (fixture / "Target/b move me.txt").exists() and not (fixture / "b move me.txt").exists(),
             "internal drop on a folder did not move the file", process)
        key("F5"); time.sleep(.3)
        names = sorted(p.name for p in fixture.iterdir() if p.is_dir()) + sorted(p.name for p in fixture.iterdir() if p.is_file())

        # Chromium web page drop zone, when installed.
        chromium = shutil.which("chromium") or shutil.which("chromium-browser")
        if chromium:
            profile = tempfile.mkdtemp(prefix="exd-", dir="/var/tmp")
            page = ("data:text/html,<title>waiting</title><body style='margin:0;height:100vh;background:%23eef'"
                    " ondragover='event.preventDefault()' ondrop='event.preventDefault();"
                    "document.title=\"dropped:\"+[...event.dataTransfer.files].map(f=>f.name).join(\",\")'>Drop</body>")
            chrome_env = dict(os.environ); chrome_env["TMPDIR"] = profile
            browser = subprocess.Popen([chromium, f"--user-data-dir={profile}", "--no-first-run", "--disable-gpu",
                                        "--no-default-browser-check", "--disable-dev-shm-usage",
                                        "--window-position=1010,0", "--window-size=560,420", f"--app={page}"],
                                       env=chrome_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            helpers.append(browser)
            try:
                wait(lambda: subprocess.run(["xdotool", "search", "--name", "waiting"], capture_output=True).returncode == 0,
                     "Chromium page missing", timeout=40)
                time.sleep(1.5)
                page_window = xdo("search", "--name", "waiting").split()[0]
                report["chromium_geometry"] = xdo("getwindowgeometry", "--shell", page_window)
                # Without a window manager a click does not move focus back.
                xdo("windowfocus", "--sync", window); time.sleep(.3)
                drag(row_of("d menu me.txt"), (1290, 250), hold=1.0, snapshot="03-chromium-hover")
                wait(lambda: subprocess.run(["xdotool", "search", "--name", "dropped:d menu me.txt"],
                                            capture_output=True).returncode == 0,
                     "Chromium did not receive the dropped file", timeout=15)
                report["chromium"] = {"received": "d menu me.txt"}
                report["captures"].append(str(capture("03-chromium-drop")))
            finally:
                browser.terminate()
                try:
                    browser.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    browser.kill()
                shutil.rmtree(profile, ignore_errors=True)
        else:
            report["chromium"] = "not installed"

        # Context menus: the file menu copies, the folder menu pastes into it,
        # the background menu creates a folder (Thunar's "New Folder").
        xdo("windowfocus", "--sync", window); time.sleep(.3)
        xdo("mousemove", "--sync", *row_of("d menu me.txt")); xdo("click", 3); time.sleep(.5)
        report["captures"].append(str(capture("04-file-menu")))
        entries = menu_labels(["view", "none", "list", "1", "1", str(fixture), str(fixture / "d menu me.txt")])
        key(*(["Down"] * downs_to(entries, "Copy")), "Return")
        time.sleep(.4)
        xdo("mousemove", "--sync", *row_of("Inbox")); xdo("click", 3); time.sleep(.5)
        report["captures"].append(str(capture("05-folder-menu")))
        entries = menu_labels(["view", "none", "list", "1", "1", str(fixture), str(fixture / "Inbox")])
        key(*(["Down"] * downs_to(entries, "Paste Into Folder")), "Return")
        wait(lambda: (fixture / "Inbox/d menu me.txt").exists(), "Copy + Paste Into Folder failed", process)
        background = (left + 300, top + 8 * row + 40)
        xdo("mousemove", "--sync", *background); xdo("click", 3); time.sleep(.5)
        report["captures"].append(str(capture("06-background-menu")))
        key("Down", "Return"); time.sleep(.4)
        key("Return")
        wait(lambda: (fixture / "New Folder").is_dir(), "Create Folder... did not create New Folder", process)
        # Open the Arrange Items submenu from the keyboard to capture radio rows.
        xdo("mousemove", "--sync", background[0] + 40, background[1] + 10); xdo("click", 3); time.sleep(.5)
        entries = menu_labels(["view", "none", "list", "1", "1", str(fixture)])
        key(*(["Down"] * downs_to(entries, "Arrange Items")), "Right")
        time.sleep(.4)
        report["captures"].append(str(capture("07-arrange-items")))
        key("Escape", "Escape")
        assert process.poll() is None
        report["result"] = "PASS"
    finally:
        for helper in helpers:
            if helper.poll() is None:
                helper.terminate()
                try:
                    helper.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    helper.kill()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        log.close()
        (OUTPUT / "report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
