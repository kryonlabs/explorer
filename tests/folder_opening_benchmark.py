#!/usr/bin/env python3
"""Compare real Explorer and Thunar folder opening on one private Xvfb.

Run with: python3 tests/private_desktop.py python3 tests/folder_opening_benchmark.py
Each sample starts a fresh application, verifies its window and process, and
measures pixels rather than trusting process-exit or shell timing. Artifacts
stay under ignored build/folder-opening.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "build/folder-opening"
WIDTH, HEIGHT = 1000, 720


def run(*args):
    return subprocess.run(list(map(str, args)), check=True, timeout=10,
                          capture_output=True, text=True).stdout.strip()


def make_fixture(home):
    root = home / "folder-opening-fixture"
    shutil.rmtree(root, ignore_errors=True)
    for name, count in (("tiny", 10), ("medium", 300), ("large", 2500)):
        folder = root / name
        folder.mkdir(parents=True)
        for index in range(count):
            (folder / f"item-{index:04d}.txt").write_text(name + " " + str(index) + "\n")
    return root


def window_for(process):
    started = time.monotonic()
    deadline = started + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("application exited early: " + str(process.returncode))
        search = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(process.pid)],
                                capture_output=True, text=True, timeout=5)
        for window in search.stdout.splitlines():
            fields = dict(item.split("=", 1) for item in
                          run("xdotool", "getwindowgeometry", "--shell", window).splitlines())
            if int(fields["WIDTH"]) > 300 and int(fields["HEIGHT"]) > 200:
                assert run("xdotool", "getwindowpid", window) == str(process.pid)
                return int(window), (time.monotonic() - started) * 1000
        time.sleep(.01)
    raise AssertionError("owned application window did not appear")


def image_bytes(window, exporter):
    pixbuf = exporter(window)
    assert pixbuf is not None
    mode = "RGBA" if pixbuf.get_has_alpha() else "RGB"
    from PIL import Image
    image = Image.frombytes(mode, (pixbuf.get_width(), pixbuf.get_height()),
                            bytes(pixbuf.get_pixels()), "raw", mode, pixbuf.get_rowstride())
    return image.convert("RGB").tobytes()


def settle(window, exporter, baseline=None, deadline_seconds=12):
    started = time.monotonic()
    deadline = started + deadline_seconds
    previous = baseline
    changed_at = None
    stable = 0
    while time.monotonic() < deadline:
        current = image_bytes(window, exporter)
        now = time.monotonic()
        if current != previous:
            stable = 0
            if changed_at is None and baseline is not None:
                changed_at = now
            previous = current
        elif changed_at is not None:
            stable += 1
            if stable >= 1:
                return {"changed_ms": None if changed_at is None else (changed_at - started) * 1000,
                        "ready_ms": (now - started) * 1000}
        elif baseline is None:
            stable += 1
            if stable >= 1:
                return {"changed_ms": None, "ready_ms": (now - started) * 1000}
        else:
            previous = current
        time.sleep(.02)
    raise AssertionError("application pixels did not reach a stable opened-folder state")


def foreign_window(display, window):
    import gi
    gi.require_version("GdkX11", "3.0")
    from gi.repository import GdkX11
    result = GdkX11.X11Window.foreign_new_for_display(display, window)
    assert result is not None
    return result


def sample(app, executable, target, home):
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk
    assert Gdk.init_check([])[0], "benchmark cannot connect to its private Xvfb"
    display = Gdk.Display.get_default()
    log_path = OUTPUT / (app + "-" + target.name + ".log")
    with log_path.open("wb") as log:
        before_launch = time.monotonic_ns()
        process = subprocess.Popen([str(executable)], cwd=home, stdout=log,
                                   stderr=subprocess.STDOUT)
        try:
            window, mapped_ms = window_for(process)
            mapped_ms += (time.monotonic_ns() - before_launch) / 1_000_000
            native_window = foreign_window(display, window)

            def exporter(_):
                return Gdk.pixbuf_get_from_window(native_window, 0, 0,
                                                  native_window.get_width(),
                                                  native_window.get_height())

            run("xdotool", "windowmove", "--sync", window, 0, 0)
            run("xdotool", "windowsize", "--sync", window, WIDTH, HEIGHT)
            run("xdotool", "windowfocus", "--sync", window)
            root = settle(window, exporter)
            startup_ready_ms = (time.monotonic_ns() - before_launch) / 1_000_000
            baseline = image_bytes(window, exporter)
            run("xdotool", "key", "--clearmodifiers", "ctrl+l")
            run("xdotool", "type", "--delay", "0", "--window", window, str(target))
            run("xdotool", "key", "--window", window, "Return")
            opened = settle(window, exporter, baseline=baseline)
            return {"app": app, "folder": target.name,
                    "entries": sum(1 for _ in target.iterdir()),
                    "mapped_ms": mapped_ms, "root_ready_ms": root["ready_ms"],
                    "startup_ready_ms": startup_ready_ms,
                    "folder_changed_ms": opened["changed_ms"],
                    "folder_ready_ms": opened["ready_ms"], "log": str(log_path)}
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def summarize(samples):
    result = {}
    for key in ("mapped_ms", "startup_ready_ms", "root_ready_ms", "folder_changed_ms", "folder_ready_ms"):
        values = [item[key] for item in samples if item.get(key) is not None]
        if values:
            result[key] = {"median_ms": statistics.median(values), "min_ms": min(values),
                           "max_ms": max(values), "samples": values}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, default=REPO / "build/explorer-desktop")
    parser.add_argument("--thunar", type=Path, default=shutil.which("thunar"))
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()
    assert os.environ.get("EXPLORER_PRIVATE_DESKTOP") == "1", "run through tests/private_desktop.py"
    assert args.executable.is_file(), args.executable
    assert args.thunar and Path(args.thunar).is_file(), "Thunar is required"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ignored = subprocess.run(["git", "check-ignore", str(OUTPUT / "report.json")],
                             cwd=REPO, capture_output=True, text=True)
    assert ignored.returncode == 0, "benchmark artifacts must be ignored"
    home = Path(os.environ["HOME"])
    targets = make_fixture(home)
    apps = {"explorer": args.executable.resolve(), "thunar": Path(args.thunar).resolve()}
    samples = []
    for iteration in range(args.iterations):
        for target in (targets / "tiny", targets / "medium", targets / "large"):
            order = ("explorer", "thunar") if iteration % 2 == 0 else ("thunar", "explorer")
            for app in order:
                samples.append(sample(app, apps[app], target, home))
                (OUTPUT / "progress.json").write_text(json.dumps(samples[-1], indent=2) + "\n")
    report = {"schema": 1, "status": "complete", "window_size": [WIDTH, HEIGHT],
              "iterations": args.iterations,
              "host": {"kernel": platform.release(), "machine": platform.machine()},
              "executables": {app: {"path": str(path), "sha256": hashlib.file_digest(
                  path.open("rb"), "sha256").hexdigest()} for app, path in apps.items()},
              "samples": samples,
              "summary": {app: {target: summarize([item for item in samples
                            if item["app"] == app and item["folder"] == target])
                            for target in ("tiny", "medium", "large")} for app in apps}}
    (OUTPUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
