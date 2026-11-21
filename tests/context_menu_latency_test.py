#!/usr/bin/env python3
"""Real popup response and application artwork on a private Xvfb display."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

from PIL import Image
from Xlib import X, display
from ui_test import require_private_display, native_chrome_geometry

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "build/context-menu-latency"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    require_private_display()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    home = Path(os.environ["HOME"])
    fixture = home / "menu-fixture"
    fixture.mkdir()
    (fixture / "test.txt").write_text("menu fixture\n")
    apps = Path(os.environ["XDG_DATA_HOME"]) / "applications"
    apps.mkdir(parents=True)
    for name, color in (("First", (240, 30, 60)), ("Second", (20, 220, 80))):
        icon = home / f"{name}.png"
        identity = str(icon)
        if name == "Second":
            icon = Path(os.environ["XDG_DATA_HOME"]) / "icons/hicolor/16x16/apps/menu-Second.png"
            icon.parent.mkdir(parents=True)
            identity = "menu-Second"
        Image.new("RGB", (32, 32), color).save(icon)
        (apps / f"menu-{name}.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName=Menu {name}\nExec=true %f\nIcon={identity}\nMimeType=text/plain;\n")
    subprocess.run(["update-desktop-database", str(apps)], check=True)
    config = Path(os.environ["XDG_CONFIG_HOME"])
    (config / "mimeapps.list").write_text(
        "[Default Applications]\ntext/plain=menu-First.desktop;\n"
        "[Added Associations]\ntext/plain=menu-First.desktop;menu-Second.desktop;\n")
    connection = display.Display()
    root = connection.screen().root
    processes = []
    log = (OUTPUT / ("baseline.log" if args.baseline else "fixed.log")).open("wb")

    def xdo(*items):
        result = subprocess.run(["xdotool", *map(str, items)], capture_output=True, text=True, timeout=10)
        if result.returncode and items[0] != "search":
            result.check_returncode()
        return result.stdout.strip()

    def wait(check, label, timeout=10):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            value = check()
            if value:
                return value
            time.sleep(.01)
        raise AssertionError(label)

    try:
        process = subprocess.Popen([str(REPO / "build/explorer-desktop")], cwd=fixture, stdout=log, stderr=log)
        processes.append(process)
        window = wait(lambda: xdo("search", "--onlyvisible", "--pid", process.pid), "Explorer window").splitlines()[0]
        xdo("windowmove", "--sync", window, 0, 0)
        xdo("windowsize", "--sync", window, 1000, 700)
        xdo("windowfocus", "--sync", window)
        xdo("key", "ctrl+2")
        time.sleep(.5)
        chrome = native_chrome_geometry()
        x = 170 + chrome["separator_width"] + 140
        y = (chrome["menu_height"] + chrome["toolbar_height"] + chrome["frame_top"] +
             chrome["header_height"] + chrome["row_height"] // 2)
        xdo("mousemove", "--sync", x, y)
        xdo("click", 1)
        time.sleep(.2)

        def pixels():
            return root.get_image(x + 8, y + 8, 250, 200, X.ZPixmap, 0xffffffff).data

        def popup():
            before = pixels()
            started = time.monotonic()
            xdo("mousedown", 3)
            xdo("mouseup", 3)
            wait(lambda: pixels() != before, "context menu did not appear")
            elapsed = (time.monotonic() - started) * 1000
            time.sleep(.15)
            return elapsed

        report = {"empty_clipboard_ms": []}
        for _ in range(3):
            report["empty_clipboard_ms"].append(popup())
            xdo("key", "Escape")
            time.sleep(.15)
        payload = home / "clipboard.txt"
        payload.write_text("copy\n" + (fixture / "test.txt").as_uri() + "\n")
        peer = subprocess.Popen([sys.executable, str(REPO / "tests/file_clipboard_test.py"),
                                 "--stall", "x-special/gnome-copied-files", str(payload)],
                                stdout=subprocess.PIPE, stderr=log, text=True)
        processes.append(peer)
        assert peer.stdout.readline().strip() == "READY"
        time.sleep(.25)
        report["slow_clipboard_ms"] = []
        for _ in range(3):
            report["slow_clipboard_ms"].append(popup())
            xdo("key", "Escape")
            time.sleep(.15)
        if not args.baseline:
            assert statistics.median(report["slow_clipboard_ms"]) < 200, report
            xdo("key", "ctrl+l", "ctrl+a")
            xdo("type", "--clearmodifiers", "--delay", 1, str(fixture))
            xdo("key", "Return")
            time.sleep(.4)
            xdo("mousemove", x, y)
            xdo("click", 1)
            time.sleep(.15)
            popup()
            subprocess.run(["import", "-window", "root", str(OUTPUT / "icons.png")], check=True)
            image = Image.open(OUTPUT / "icons.png").convert("RGB")
            red = sum(1 for r, g, b in image.crop((x, y, x + 400, y + 50)).get_flattened_data()
                      if r > 210 and g < 65 and b < 100)
            assert red >= 150, "default application's red icon is missing"
            xdo("key", "Down", "Down", "Right")
            time.sleep(.2)
            subprocess.run(["import", "-window", "root", str(OUTPUT / "submenu-icons.png")], check=True)
            image = Image.open(OUTPUT / "submenu-icons.png").convert("RGB")
            green = sum(1 for r, g, b in image.crop((x + 250, y, 1000, y + 150)).get_flattened_data()
                        if r < 50 and g > 190 and b < 110)
            assert green >= 150, "alternate application's green icon is missing"
            report.update(default_icon_pixels=red, alternate_icon_pixels=green)
            xdo("key", "Escape", "Escape")
            thunar = subprocess.Popen(["thunar", str(home)], stdout=log, stderr=log)
            processes.append(thunar)
            native = wait(lambda: xdo("search", "--onlyvisible", "--pid", thunar.pid), "Thunar window").splitlines()[0]
            xdo("windowmove", "--sync", native, 0, 0)
            xdo("windowsize", "--sync", native, 1000, 700)
            xdo("windowfocus", "--sync", native)
            xdo("key", "ctrl+2")
            time.sleep(.6)
            xdo("mousemove", x, y)
            xdo("click", 1)
            time.sleep(.2)
            report["thunar_slow_clipboard_ms"] = []
            for _ in range(3):
                report["thunar_slow_clipboard_ms"].append(popup())
                xdo("key", "Escape")
                time.sleep(.15)
        destination = OUTPUT / ("baseline.json" if args.baseline else "fixed.json")
        destination.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        connection.close()
        log.close()


if __name__ == "__main__":
    main()
