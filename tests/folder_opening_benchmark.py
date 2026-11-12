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
import xml.etree.ElementTree as ET

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


def window_for(process, started):
    deadline = started + 20
    mapped_at = None
    candidate = None
    stable_since = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("application exited early: " + str(process.returncode))
        search = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(process.pid)],
                                capture_output=True, text=True, timeout=5)
        for window in search.stdout.splitlines():
            try:
                geometry = run("xdotool", "getwindowgeometry", "--shell", window)
                owner = run("xdotool", "getwindowpid", window)
            except subprocess.CalledProcessError:
                continue
            fields = dict(item.split("=", 1) for item in geometry.splitlines())
            if int(fields["WIDTH"]) > 300 and int(fields["HEIGHT"]) > 200:
                assert owner == str(process.pid)
                now = time.monotonic()
                if mapped_at is None:
                    mapped_at = now
                if candidate != window:
                    candidate, stable_since = window, now
                elif now - stable_since >= .05:
                    return int(window), (mapped_at - started) * 1000
            break
        time.sleep(.005)
    raise AssertionError("owned application window did not become stable")


def image_bytes(window, exporter):
    pixbuf = exporter(window)
    assert pixbuf is not None
    return bytes(pixbuf.get_pixels())


def settle(window, exporter, baseline=None, deadline_seconds=12, started=None):
    if started is None:
        started = time.monotonic()
    deadline = started + deadline_seconds
    previous = baseline
    changed_at = None
    stable_since = None
    ready_at = None
    while time.monotonic() < deadline:
        current = image_bytes(window, exporter)
        now = time.monotonic()
        if current != previous:
            stable_since = now
            ready_at = now
            if changed_at is None and baseline is not None:
                changed_at = now
            previous = current
        elif changed_at is not None or baseline is None:
            if stable_since is not None and now - stable_since >= .3:
                return {"changed_ms": None if changed_at is None else (changed_at - started) * 1000,
                        "ready_ms": (ready_at - started) * 1000}
        else:
            previous = current
        time.sleep(.005)
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
            window, mapped_ms = window_for(process, before_launch / 1_000_000_000)
            native_window = None

            def exporter(_):
                return Gdk.pixbuf_get_from_window(native_window, 0, 0,
                                                  native_window.get_width(),
                                                  native_window.get_height())

            run("xdotool", "windowmove", "--sync", window, 0, 0)
            run("xdotool", "windowsize", "--sync", window, WIDTH, HEIGHT)
            run("xdotool", "windowfocus", "--sync", window)
            # A foreign GDK window caches its initial geometry. Create it after
            # resizing so both captures contain the full, same-sized viewport.
            native_window = foreign_window(display, window)
            assert (native_window.get_width(), native_window.get_height()) == (WIDTH, HEIGHT)
            root = settle(window, exporter, started=before_launch / 1_000_000_000)
            startup_ready_ms = root["ready_ms"]
            # Observe file rows, excluding toolbar/sidebar/status and native
            # scrollbar fades. Full-window captures remain available to inspect.
            response_exporter = lambda _: Gdk.pixbuf_get_from_window(
                native_window, 200, 150, WIDTH-224, HEIGHT-190)
            run("xdotool", "key", "--clearmodifiers", "ctrl+l")
            run("xdotool", "type", "--delay", "0", "--window", window, str(target))
            # Return measures navigation handling only. Let the completed
            # toolbar edit settle, then record both pixels immediately before
            # the submission key reaches the application.
            settle(window, response_exporter)
            response_baseline = image_bytes(window, response_exporter)
            submitted_at = time.monotonic()
            run("xdotool", "key", "--delay", "0", "--window", window, "Return")
            opened = settle(window, response_exporter, baseline=response_baseline,
                            started=submitted_at)
            exporter(window).savev(str(OUTPUT / (app + "-" + target.name + ".png")), "png", [], [])
            return {"app": app, "folder": target.name,
                    "entries": sum(1 for _ in target.iterdir()),
                    "mapped_ms": mapped_ms, "root_ready_ms": startup_ready_ms - mapped_ms,
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
    # Explorer starts in details view with 48px icons. Match that workload in
    # Thunar, using only this private session's configuration.
    channel = ET.Element("channel", name="thunar", version="1.0")
    for name, value in (("last-view", "ThunarDetailsView"),
                        ("last-details-view-zoom-level", "THUNAR_ZOOM_LEVEL_75_PERCENT"),
                        ("last-location-bar", "ThunarLocationEntry")):
        ET.SubElement(channel, "property", name=name, type="string", value=value)
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "xfce4/xfconf/xfce-perchannel-xml/thunar.xml"
    config.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(channel).write(config, encoding="utf-8")
    apps = {"explorer": args.executable.resolve(), "thunar": Path(args.thunar).resolve()}
    samples = []
    for iteration in range(args.iterations):
        for target in (targets / "tiny", targets / "medium", targets / "large"):
            order = ("explorer", "thunar") if iteration % 2 == 0 else ("thunar", "explorer")
            for app in order:
                samples.append(sample(app, apps[app], target, home))
                (OUTPUT / "progress.json").write_text(json.dumps(samples[-1], indent=2) + "\n")
    report = {"schema": 1, "status": "complete", "window_size": [WIDTH, HEIGHT],
              "iterations": args.iterations, "view": "details", "icon_size": 48,
              "navigation_region": [200, 150, WIDTH-224, HEIGHT-190],
              "stability_verification_ms": 300,
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
