#!/usr/bin/env python3
"""Capture real Thunar/Shelf on an owned Xvfb; exact parity is an assertion.

Run with build-queue -- python3 tests/thunar_visual_test.py [--reference-only].
Add --populated-home for a separate 960x1020 Home/bookmark/scroll comparison.
Artifacts persist in ignored build/thunar-visual. No owner settings are changed.
The reference-only mode never opens or reads the Shelf executable.
"""
import argparse
from collections import Counter
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "build/thunar-visual"
WIDTH, HEIGHT = 1000, 760


def run(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, timeout=30,
                          capture_output=True, text=True, **kwargs).stdout.strip()


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def discover():
    """Read only the bounded owner settings needed by these two applications."""
    import configparser
    home = Path.home()
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    values = {}
    xml = config / "xfce4/xfconf/xfce-perchannel-xml/xsettings.xml"
    if xml.is_file():
        assert xml.stat().st_size <= 131072, "unbounded XSettings file"
        tree = ET.fromstring(xml.read_bytes())
        for group, key, prop in (("Net", "theme", "ThemeName"),
                                 ("Net", "icons", "IconThemeName"),
                                 ("Gtk", "font", "FontName")):
            node = tree.find(f"./property[@name='{group}']/property[@name='{prop}']")
            if node is not None:
                values[key] = node.get("value")
    ini = config / "gtk-3.0/settings.ini"
    if ini.is_file():
        assert ini.stat().st_size <= 131072
        parser = configparser.ConfigParser()
        parser.read(ini)
        for key, prop in (("theme", "gtk-theme-name"), ("icons", "gtk-icon-theme-name"),
                          ("font", "gtk-font-name")):
            if parser.has_option("Settings", prop):
                values.setdefault(key, parser.get("Settings", prop))
    assert all(values.get(k) for k in ("theme", "icons", "font")), values
    for key in ("theme", "icons"):
        assert Path(values[key]).name == values[key] and values[key] not in (".", "..")
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    dirs = [data, *map(Path, os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"))]
    themes = [home / ".themes", *(p / "themes" for p in dirs)]
    source = next((p / values["theme"] for p in themes
                   if (p / values["theme"] / "gtk-3.0/gtk.css").is_file()), None)
    assert source, "selected GTK3 theme is unavailable"
    values.update(theme_source=str(source), data_dirs=list(map(str, dirs)),
                  icon_dirs=[str(home / ".icons"), *(str(p / "icons") for p in dirs)])
    return values


def prepare(settings):
    assert run("git", "check-ignore", str(OUTPUT / "report.json"), cwd=REPO), "artifacts must be ignored"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Remove only our previous disposable runtime, retaining reference evidence.
    private = OUTPUT / "private"
    if private.exists():
        shutil.rmtree(private)
    private.mkdir(mode=0o700)
    env = os.environ.copy()
    for key in ("DISPLAY", "WAYLAND_DISPLAY", "WAYLAND_SOCKET", "XAUTHORITY",
                "DBUS_SESSION_BUS_ADDRESS", "SESSION_MANAGER", "ICEAUTHORITY",
                "GTK_THEME", "GTK2_RC_FILES", "GTK_PATH", "GDK_BACKEND"):
        env.pop(key, None)
    for key, folder in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"),
                        ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache"),
                        ("XDG_STATE_HOME", "state"), ("XDG_RUNTIME_DIR", "runtime"),
                        ("TMPDIR", "tmp")):
        path = private / folder
        path.mkdir(mode=0o700)
        env[key] = str(path)
    # GTK searches XDG data roots for themes. Copy the complete discovered theme
    # (including CSS dependencies), never synthesize CSS or approximate colors.
    target = private / "data/themes" / settings["theme"]
    shutil.copytree(settings["theme_source"], target)
    settings["private_theme_copy"] = str(target)
    env.update(YUE_DESKTOP_RECOVERY="0", SDL_VIDEODRIVER="x11", GDK_BACKEND="x11",
               GTK_USE_PORTAL="0",
               NO_AT_BRIDGE="1", LC_ALL="C.UTF-8",
               XDG_DATA_DIRS=":".join(settings["data_dirs"]))
    config = private / "config"
    gtk = config / "gtk-3.0/settings.ini"
    gtk.parent.mkdir(parents=True)
    gtk.write_text("[Settings]\n" + "\n".join((
        f"gtk-theme-name={settings['theme']}", f"gtk-icon-theme-name={settings['icons']}",
        f"gtk-font-name={settings['font']}", "gtk-enable-animations=false")) + "\n")
    root = ET.Element("channel", name="xsettings", version="1.0")
    for group, props in (("Net", (("ThemeName", settings["theme"]), ("IconThemeName", settings["icons"]))),
                         ("Gtk", (("FontName", settings["font"]),))):
        parent = ET.SubElement(root, "property", name=group, type="empty")
        for name, value in props:
            ET.SubElement(parent, "property", name=name, type="string", value=value)
    xml = config / "xfce4/xfconf/xfce-perchannel-xml/xsettings.xml"
    xml.parent.mkdir(parents=True)
    ET.ElementTree(root).write(xml, encoding="utf-8")
    # Match the owner's detailed view and large icons without importing bookmarks
    # or directory contents. Both apps navigate the exact same fixture path.
    root = ET.Element("channel", name="thunar", version="1.0")
    for name, kind, value in (("last-view", "string", "ThunarDetailsView"),
                               ("last-details-view-zoom-level", "string", "THUNAR_ZOOM_LEVEL_75_PERCENT"),
                               ("last-location-bar", "string", "ThunarLocationEntry"),
                               ("last-show-hidden", "bool", "false")):
        ET.SubElement(root, "property", name=name, type=kind, value=value)
    ET.ElementTree(root).write(xml.with_name("thunar.xml"), encoding="utf-8")
    (OUTPUT / "environment.json").write_text(json.dumps(settings, indent=2) + "\n")
    return env


class QuietFilesystem:
    """Own a bounded tmpfs only inside our same-UID user/mount namespace."""
    def __init__(self, path):
        assert not path.is_symlink()
        self.path = path.resolve()
        identity = list(map(int, Path("/proc/self/uid_map").read_text().split()))
        assert identity == [os.getuid(), os.getuid(), 1] and os.getuid() != 0, identity
        assert self.path.is_relative_to(OUTPUT.resolve())
        self.path.mkdir(exist_ok=True)
        assert not self.path.is_symlink() and not self.path.is_mount()
        self.lib = ctypes.CDLL(None, use_errno=True)
        self.lib.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p]
        self.lib.umount2.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self.encoded = os.fsencode(self.path)
        assert self.lib.mount(b"tmpfs", self.encoded, b"tmpfs", 14, b"size=32m") == 0, os.strerror(ctypes.get_errno())
        assert self.path.is_mount() and not any(self.path.iterdir())
        self.report = {"kind": "private-tmpfs", "uid": os.getuid(), "path": str(self.path), "start": self.sample()}

    def sample(self):
        value = os.statvfs(self.path)
        return {"size_bytes": value.f_blocks * value.f_frsize, "free_bytes": value.f_bavail * value.f_frsize, "device": self.path.stat().st_dev}

    def close(self):
        self.report["end"] = self.sample()
        result = self.lib.umount2(self.encoded, 0)
        self.report["unmounted"] = result == 0 and not self.path.is_mount()
        assert result == 0, os.strerror(ctypes.get_errno())


def fixture(populated_home=False):
    from PIL import Image
    if populated_home:
        path = Path(os.environ["HOME"])
        folders = ["Android", "bin", "Desktop", "Documents", "Downloads", "Games",
                   "Music", "Pictures", "Projects", "Public", "Templates", "Videos",
                   "Workspace", "storage"] + [f"Folder {i:02d}" for i in range(26)]
        for name in folders:
            (path / name).mkdir()
        for i in range(24):
            (path / f"Notes {i:02d}.txt").write_text(f"Synthetic Home fixture {i:02d}.\n")
        (path / "Linked Documents").symlink_to("Documents", target_is_directory=True)
        (path / "Linked Notes.txt").symlink_to("Notes 00.txt")
        Image.new("RGB", (64, 64), (30, 120, 210)).save(path / "Image.png")
        config = Path(os.environ["XDG_CONFIG_HOME"])
        (config / "user-dirs.dirs").write_text("".join(
            f'XDG_{key}_DIR="{path / folder}"\n' for key, folder in (
                ("DESKTOP", "Desktop"), ("DOCUMENTS", "Documents"),
                ("DOWNLOAD", "Downloads"), ("MUSIC", "Music"),
                ("PICTURES", "Pictures"), ("PUBLICSHARE", "Public"),
                ("TEMPLATES", "Templates"), ("VIDEOS", "Videos"))))
        (config / "gtk-3.0/bookmarks").write_text("".join(
            (path / name).as_uri() + "\n" for name in (
                "Pictures", "Documents", "Downloads", "Games", "Projects",
                "Workspace", "storage", "Videos")) + path.as_uri() + "\n")
        for item in path.iterdir():
            os.utime(item, (1700000000, 1700000000), follow_symlinks=False)
        # Local calendar dates exercise Thunar's relative date style across
        # midnight and DST without changing the fixed historical fixture.
        import datetime
        today = datetime.date.today()
        for name, age in (("Android", 0), ("bin", 1), ("Desktop", 3),
                          ("Documents", 8)):
            stamp = datetime.datetime.combine(today - datetime.timedelta(days=age),
                                              datetime.time()).timestamp()
            os.utime(path / name, (stamp, stamp), follow_symlinks=False)
        return path
    path = OUTPUT / "fixture"
    assert path.is_mount() and not any(path.iterdir()), "fixture must be an empty private mount"
    for name in ("01 Folder", "Documents", "Pictures"):
        (path / name).mkdir()
    (path / "04 Notes.txt").write_text("Shelf and Thunar native comparison.\n")
    Image.new("RGB", (64, 64), (30, 120, 210)).save(path / "05 Image.png")
    (path / "06 Folder link").symlink_to("01 Folder", target_is_directory=True)
    (path / "07 File link.txt").symlink_to("04 Notes.txt")
    (path / "08 Broken link").symlink_to("absent")
    for item in path.iterdir():
        os.utime(item, (1700000000, 1700000000), follow_symlinks=False)
    user_dirs = Path(os.environ["XDG_CONFIG_HOME"]) / "user-dirs.dirs"
    user_dirs.write_text(f'XDG_DOCUMENTS_DIR="{path}/Documents"\nXDG_PICTURES_DIR="{path}/Pictures"\n')
    return path


def native_reference(path, settings):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gio, Pango
    assert Gtk.init_check()[0], "GTK cannot connect to private Xvfb"
    gtk = Gtk.Settings.get_default()
    observed = {key: gtk.get_property(prop) for key, prop in (
        ("theme", "gtk-theme-name"), ("icons", "gtk-icon-theme-name"), ("font", "gtk-font-name"))}
    assert observed == {k: settings[k] for k in observed}, (observed, settings)
    icons = Gtk.IconTheme.get_default()
    # Resolve through the same native search order GTK uses for application icons.
    for directory in settings["icon_dirs"]:
        if directory not in icons.get_search_path():
            icons.append_search_path(directory)
    result = {"settings": observed, "icon_search_path": icons.get_search_path(), "icons": [], "styles": {}}
    icon_output = OUTPUT / "native-icons"
    icon_output.mkdir(exist_ok=True)
    for item in sorted(path.iterdir()):
        info = Gio.File.new_for_path(str(item)).query_info("standard::icon,standard::content-type", Gio.FileQueryInfoFlags.NONE, None)
        icon = info.get_icon()
        resolved = icons.lookup_by_gicon(icon, 48, Gtk.IconLookupFlags.FORCE_SIZE)
        assert resolved, f"GTK failed to resolve {item.name}: {icon}"
        resolved.load_icon().savev(str(icon_output / (item.name + ".png")), "png", [], [])
        result["icons"].append({"file": item.name, "gio_icon": icon.to_string(),
                                "mime": info.get_content_type(), "asset": resolved.get_filename()})
    for name, widget in (("tree", Gtk.TreeView()), ("menu", Gtk.MenuBar()),
                         ("toolbar", Gtk.Toolbar()), ("entry", Gtk.Entry()), ("button", Gtk.Button())):
        ctx = widget.get_style_context()
        result["styles"][name] = {"font": ctx.get_property("font", Gtk.StateFlags.NORMAL).to_string()}
        for state_name, state in (("normal", Gtk.StateFlags.NORMAL), ("selected", Gtk.StateFlags.SELECTED)):
            result["styles"][name][state_name] = {
                "foreground": ctx.get_color(state).to_string(),
                "background": ctx.get_background_color(state).to_string()}
        layout = widget.create_pango_layout("Documents")
        result["styles"][name]["Documents_pixels"] = list(layout.get_pixel_size())
    # Real GTK image hierarchy matters: themes can transform toolbar artwork
    # after loading its pixbuf. Record that native render instead of guessing
    # a smaller icon category from its visible ink.
    import cairo
    window = Gtk.OffscreenWindow()
    window.get_style_context().add_class("thunar")
    toolbar = Gtk.Toolbar()
    toolbar.set_style(Gtk.ToolbarStyle.ICONS)
    toolbar.set_orientation(Gtk.Orientation.HORIZONTAL)
    toolbar.set_icon_size(Gtk.IconSize.LARGE_TOOLBAR)
    window.add(toolbar)
    button = Gtk.ToolButton()
    image = Gtk.Image.new_from_icon_name("go-up-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
    button.set_icon_widget(image)
    toolbar.insert(button, -1)
    window.set_default_size(200, 50)
    window.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    context = image.get_style_context()
    def allocation(widget):
        box=widget.get_allocation()
        return [box.x,box.y,box.width,box.height]
    control=button.get_child()
    control_margin=control.get_style_context().get_margin(Gtk.StateFlags.NORMAL)
    result["native_toolbar_allocations"]={"item":allocation(button),"control":allocation(control),"image":allocation(image),
        "button_classes":control.get_style_context().list_classes(),
        "button_margin":[control_margin.left,control_margin.top,control_margin.right,control_margin.bottom]}
    valid, icon_width, icon_height = Gtk.icon_size_lookup(Gtk.IconSize.LARGE_TOOLBAR)
    assert valid
    flags = Gtk.IconLookupFlags.USE_BUILTIN | Gtk.IconLookupFlags.DIR_LTR
    result["toolbar_icons"] = {"category": "GTK_ICON_SIZE_LARGE_TOOLBAR",
                               "category_pixels": [icon_width, icon_height],
                               "lookup_flags": int(flags), "style_path": context.get_path().to_string(),
                               "resolved": []}
    try:
        for name in ("go-previous-symbolic", "go-next-symbolic", "go-up-symbolic",
                     "go-home-symbolic", "system-search-symbolic"):
            resolved = icons.lookup_icon_for_scale(name, icon_width, 1, flags)
            assert resolved, f"GTK failed to resolve toolbar icon {name}"
            pixbuf, symbolic = resolved.load_symbolic_for_context(context)
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, icon_width, icon_height)
            Gtk.render_icon(context, cairo.Context(surface), pixbuf,
                            (icon_width - pixbuf.get_width()) / 2,
                            (icon_height - pixbuf.get_height()) / 2)
            target = icon_output / (name + "-toolbar.png")
            surface.write_to_png(str(target))
            from PIL import Image
            with Image.open(target) as rendered:
                ink = rendered.getbbox()
            result["toolbar_icons"]["resolved"].append({
                "name": name, "asset": resolved.get_filename(), "symbolic": symbolic,
                "loaded_pixels": [pixbuf.get_width(), pixbuf.get_height()],
                "gtk_rendered_ink_bounds": ink, "native_render": str(target)})
    finally:
        window.destroy()
    result["gtk_version"] = [Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()]
    result["theme_css_sha256"] = digest(Path(settings["theme_source"]) / "gtk-3.0/gtk.css")
    assert result["theme_css_sha256"] == digest(Path(settings["private_theme_copy"]) / "gtk-3.0/gtk.css")
    result["named_icons"] = []
    for name in ("go-previous", "go-next", "go-up", "go-home", "edit-find", "user-home",
                 "computer", "drive-harddisk", "user-trash", "document-open-recent",
                 "network-workgroup", "emblem-symbolic-link", "emblem-unreadable"):
        resolved = icons.lookup_icon(name, 24, Gtk.IconLookupFlags.FORCE_SIZE)
        result["named_icons"].append({"name": name, "asset": resolved.get_filename() if resolved else None})
    return result


def window_for(proc):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        assert proc.poll() is None, f"owned app exited: {proc.returncode}"
        search = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(proc.pid)],
                                capture_output=True, text=True, timeout=5)
        for window in search.stdout.splitlines():
            geometry = run("xdotool", "getwindowgeometry", "--shell", window)
            fields = dict(line.split("=", 1) for line in geometry.splitlines())
            if int(fields["WIDTH"]) > 300 and int(fields["HEIGHT"]) > 200:
                assert run("xdotool", "getwindowpid", window) == str(proc.pid)
                return window
        time.sleep(.1)
    raise AssertionError("missing owned application window")


def capture(name, command, path, populated_home=False, probe_locations=False):
    from PIL import Image
    with (OUTPUT / (name + ".log")).open("wb") as log:
        proc = subprocess.Popen(list(map(str, command)), cwd=path, stdout=log, stderr=log)
        try:
            window = window_for(proc)
            # SDL's initial centered position can extend beyond Xvfb after a
            # resize. ImageMagick clips invisible pixels even when X11 reports
            # the requested client size, so place the entire window on screen.
            run("xdotool", "windowmove", "--sync", window, 0, 0)
            run("xdotool", "windowsize", "--sync", window, WIDTH, HEIGHT)
            geometry = dict(line.split("=", 1) for line in
                            run("xdotool", "getwindowgeometry", "--shell", window).splitlines())
            assert (int(geometry["WIDTH"]), int(geometry["HEIGHT"])) == (WIDTH, HEIGHT), geometry
            assert (int(geometry["X"]), int(geometry["Y"])) == (0, 0), geometry
            run("xdotool", "windowfocus", "--sync", window)
            # Read this verified owned window directly. Spawning ImageMagick
            # and compressing three full frames can exceed GTK's tooltip
            # deadline on a busy host before the hover pixels are compared.
            import gi
            gi.require_version("GdkX11", "3.0")
            from gi.repository import Gdk, GdkX11
            native_window = GdkX11.X11Window.foreign_new_for_display(
                Gdk.Display.get_default(), int(window))
            assert native_window is not None
            def stable_capture(suffix, deadline=None, interval=.35, earliest=None):
                target = OUTPUT / (name + suffix + ".png")
                previous = None
                deadline = deadline if deadline is not None else time.monotonic() + 12
                # Native overlay scrollbars can remain unchanged during their
                # idle delay before fading. Include that delay in idle states.
                earliest = earliest if earliest is not None else time.monotonic() + 2
                stable = 0
                while time.monotonic() < deadline:
                    assert proc.poll() is None
                    pixels = Gdk.pixbuf_get_from_window(native_window, 0, 0, WIDTH, HEIGHT)
                    assert pixels is not None
                    mode = "RGBA" if pixels.get_has_alpha() else "RGB"
                    shot = Image.frombytes(mode, (pixels.get_width(), pixels.get_height()),
                                           bytes(pixels.get_pixels()), "raw", mode,
                                           pixels.get_rowstride()).convert("RGB")
                    assert shot.size == (WIDTH, HEIGHT), shot.size
                    current = shot.tobytes()
                    stable = stable + 1 if current == previous else 0
                    if stable >= 2 and time.monotonic() >= earliest:
                        shot.save(target)
                        return {"size": [WIDTH, HEIGHT], "stable_frames": 3,
                                "x11_geometry": geometry,
                                "observed_geometry": observe_geometry(target),
                                "window_pid_verified": True, "screenshot": str(target)}
                    previous = current
                    time.sleep(interval)
                raise AssertionError(f"{name}{suffix} capture never stabilized")

            # Wait for each native input transition to finish before sending
            # the next action. A stable final screenshot alone cannot prove
            # an earlier sidebar click reached the intended view.
            stable_capture("-startup-ready")
            for key in ("ctrl+l", "ctrl+a"):
                run("xdotool", "key", "--clearmodifiers", key)
                time.sleep(.15)
            run("xdotool", "type", "--clearmodifiers", "--delay", "1", path)
            run("xdotool", "key", "Return")
            stable_capture("-navigation-ready")
            run("xdotool", "key", "--clearmodifiers", "ctrl+2")
            stable_capture("-view-ready")
            # The populated state selects Home in the sidebar, matching the
            # supplied reference. Its body has no blank area to click.
            focus = (70, 143) if populated_home else (WIDTH - 40, HEIGHT - 60)
            run("xdotool", "mousemove", "--window", window, *focus)
            run("xdotool", "click", "1")
            run("xdotool", "mousemove", "--window", window, WIDTH - 2, HEIGHT - 2)
            result = stable_capture("")
            run("xdotool", "mousemove", "--window", window, 250, 110)
            run("xdotool", "click", "1")
            run("xdotool", "mousemove", "--window", window, WIDTH - 2, HEIGHT - 2)
            time.sleep(.4)
            result["selected"] = stable_capture("-selected")
            # Compare the control-hover state before GTK's separate tooltip
            # popup appears. Reset browse mode without changing GTK settings,
            # then enforce the actual native initial-tooltip deadline.
            from gi.repository import Gtk
            native_settings = Gtk.Settings.get_default()
            tooltip_delay = native_settings.get_property("gtk-tooltip-timeout")
            browse_reset = native_settings.get_property("gtk-tooltip-browse-mode-timeout")
            assert tooltip_delay > 0, "Native tooltip delay leaves no pre-tooltip hover state"
            run("xdotool", "mousemove", WIDTH + 50, 45)
            time.sleep(max(tooltip_delay, browse_reset) / 1000 + .1)
            hover_start = time.monotonic()
            run("xdotool", "mousemove", "--window", window, 90, 45)
            # Include native hover transitions before checking stable pixels;
            # a few identical fast samples can precede the next GTK frame.
            result["hover"] = stable_capture("-hover", hover_start + tooltip_delay / 1000,
                                             .02, hover_start + .2)
            elapsed = (time.monotonic() - hover_start) * 1000
            assert elapsed < tooltip_delay, ("Hover capture reached native tooltip deadline", elapsed, tooltip_delay)
            result["hover"]["timing"] = {"state": "control-hover-before-tooltip",
                "native_tooltip_delay_ms": tooltip_delay, "native_browse_reset_ms": browse_reset,
                "capture_elapsed_ms": elapsed, "popup_parity": "not tested"}
            # Record whether requested transitions actually changed rendered pixels.
            with Image.open(result["screenshot"]) as a, Image.open(result["selected"]["screenshot"]) as b:
                result["selection_changed_pixels"] = a.convert("RGB").tobytes() != b.convert("RGB").tobytes()
            with Image.open(result["selected"]["screenshot"]) as a, Image.open(result["hover"]["screenshot"]) as b:
                result["hover_changed_pixels"] = a.convert("RGB").tobytes() != b.convert("RGB").tobytes()
            if populated_home:
                run("xdotool", "mousemove", "--window", window, WIDTH - 2, HEIGHT - 2)
                run("xdotool", "key", "--clearmodifiers", "End")
                time.sleep(.6)
                result["scrolled"] = stable_capture("-scrolled")
                with Image.open(result["selected"]["screenshot"]) as a, Image.open(result["scrolled"]["screenshot"]) as b:
                    result["scroll_changed_pixels"] = a.convert("RGB").tobytes() != b.convert("RGB").tobytes()
                assert result["scroll_changed_pixels"], f"{name}: populated Home did not scroll"
            if probe_locations:
                assert not populated_home, "sidebar route probe uses the standard fixture"
                result["native_sidebar_routes"] = []
                for label, y, expected in (("Computer", 113, "computer:///"),
                                           ("Recent", 173, "recent:///"),
                                           ("Browse Network", 330, "network:///")):
                    run("xdotool", "mousemove", "--window", window, 80, y)
                    run("xdotool", "click", "1")
                    deadline = time.monotonic() + 12
                    copied = b""
                    while time.monotonic() < deadline:
                        assert proc.poll() is None
                        run("xdotool", "key", "--clearmodifiers", "ctrl+l")
                        time.sleep(.15)
                        run("xdotool", "key", "--clearmodifiers", "ctrl+a", "ctrl+c")
                        offered = subprocess.run([sys.executable, str(REPO / "tests/file_clipboard_test.py"),
                                                  "--read", "UTF8_STRING"],
                                                 capture_output=True, timeout=10)
                        copied = offered.stdout
                        run("xdotool", "key", "--clearmodifiers", "Escape")
                        if offered.returncode == 0 and copied.decode().rstrip("/") == expected.rstrip("/"):
                            break
                        time.sleep(.2)
                    passed = offered.returncode == 0 and copied.decode().rstrip("/") == expected.rstrip("/")
                    result["native_sidebar_routes"].append({
                        "label": label, "click": [80, y], "observed_location": copied.decode(),
                        "expected_uri": expected, "passed": passed})
            return result
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def observe_geometry(target):
    """Record pixel evidence, with no expected layout supplied by Shelf code."""
    from PIL import Image
    with Image.open(target) as image:
        image = image.convert("RGB")
        spans = {}
        for y in (30, 65, 90, 150, 600):
            row = [image.getpixel((x, y)) for x in range(WIDTH)]
            runs = []
            start = 0
            for x in range(1, WIDTH + 1):
                if x == WIDTH or row[x] != row[start]:
                    if x - start >= 12:
                        runs.append({"x": start, "width": x - start, "rgb": row[start]})
                    start = x
            spans[str(y)] = runs
        # This strip covers Thunar's first file icon. Preserve literal measured
        # spans; they are evidence, not an assumption that Shelf uses this column.
        occupied = []
        for y in range(90, HEIGHT - 30):
            pixels = [image.getpixel((x, y)) for x in range(174, 224)]
            if sum(max(p) - min(p) > 70 and max(p) > 110 for p in pixels) >= 3:
                occupied.append(y)
        bands = []
        for y in occupied:
            if bands and bands[-1][1] + 1 == y:
                bands[-1][1] = y
            else:
                bands.append([y, y])
        return {"solid_horizontal_runs": spans, "saturated_icon_strip_x": [174, 224],
                "saturated_icon_strip_y_spans": bands}


def compare(suffix=""):
    from PIL import Image, ImageChops, ImageStat
    reference = Image.open(OUTPUT / ("thunar" + suffix + ".png")).convert("RGB")
    shelf = Image.open(OUTPUT / ("shelf" + suffix + ".png")).convert("RGB")
    diff = ImageChops.difference(reference, shelf)
    diff.save(OUTPUT / ("difference" + suffix + ".png"))
    pair = Image.new("RGB", (WIDTH * 2, HEIGHT))
    pair.paste(shelf, (0, 0))
    pair.paste(reference, (WIDTH, 0))
    pair.save(OUTPUT / ("paired" + suffix + ".png"))
    regions = {}
    for name, rect in (("whole_window", (0, 0, WIDTH, HEIGHT)),
                       ("top_120px", (0, 0, WIDTH, 120)),
                       ("left_170px", (0, 120, 170, HEIGHT - 30)),
                       ("file_area", (170, 120, WIDTH, HEIGHT - 30))):
        a, b = reference.crop(rect), shelf.crop(rect)
        delta = ImageChops.difference(a, b)
        same = sum(p == (0, 0, 0) for p in delta.getdata())
        colors_a, colors_b = Counter(a.getdata()), Counter(b.getdata())
        regions[name] = {"bounds": rect, "mean_absolute_channel_error": sum(ImageStat.Stat(delta).mean) / 3,
                         "identical_pixel_fraction": same / (a.width * a.height),
                         "thunar_dominant_colors": colors_a.most_common(5),
                         "shelf_dominant_colors": colors_b.most_common(5)}
    return {"exact_pixel_parity": diff.getbbox() is None, "difference_bounds": diff.getbbox(), "regions": regions,
            "font_parity": "unverified independently; covered by exact pixel assertion",
            "geometry_parity": "window dimensions matched; internal geometry covered by exact pixel assertion",
            "icon_parity": "native GTK assets resolved; Shelf raster parity covered by exact pixel assertion"}


def worker(options):
    # The outer process alone creates this environment, starting from scrubbed
    # display/session variables. Independently prove the X server is our Xvfb.
    display = os.environ["DISPLAY"]
    number = display.removeprefix(":").split(".")[0]
    pid = int(Path(f"/tmp/.X{number}-lock").read_text().strip())
    assert Path(f"/proc/{pid}/comm").read_text().strip() == "Xvfb"
    assert os.environ["YUE_DESKTOP_RECOVERY"] == "0"
    settings = json.loads((OUTPUT / "environment.json").read_text())
    report = {"status": "error", "display": display, "private_xvfb_pid": pid,
              "mode": "reference-only" if options.reference_only else "paired",
              "fixture_state": "populated-home" if options.populated_home else "standard"}
    daemon = None
    filesystem = None
    try:
        filesystem = QuietFilesystem(Path(os.environ["HOME"]) if options.populated_home else OUTPUT / "fixture")
        report["filesystem"] = filesystem.report
        with (OUTPUT / "xfsettingsd.log").open("wb") as log:
            daemon = subprocess.Popen(["xfsettingsd", "--no-daemon"], stdout=log, stderr=log)
        time.sleep(.7)
        assert daemon.poll() is None, "private XSettings manager exited"
        path = fixture(options.populated_home)
        report["fixture"] = str(path)
        if options.populated_home:
            report["fixture_contents"] = {
                "directories": sum(p.is_dir() for p in path.iterdir()),
                "files": sum(p.is_file() for p in path.iterdir()),
                "bookmarks": 9, "home_sidebar_click": [70, 143],
                "viewport": [WIDTH, HEIGHT], "overflow_action": "End"}
        filesystem.report["fixture_ready"] = filesystem.sample()
        report["native_gtk"] = native_reference(path, settings)
        # Both apps start at private Home, then take the same Ctrl+L navigation
        # into the fixture. This gives their Back/Forward controls equal history.
        report["initial_location"] = os.environ["HOME"]
        report["thunar"] = capture("thunar", ["thunar", os.environ["HOME"]], path,
                                   options.populated_home, options.probe_locations)
        filesystem.report["after_thunar"] = filesystem.sample()
        assert filesystem.report["fixture_ready"] == filesystem.report["after_thunar"], "native browsing changed fixture filesystem"
        # Thunar writes its actual allocated column widths on clean exit.
        # Record native geometry rather than estimating boundaries from pixels.
        preferences = Path(os.environ["XDG_CONFIG_HOME"]) / "xfce4/xfconf/xfce-perchannel-xml/thunar.xml"
        if preferences.is_file():
            assert preferences.stat().st_size <= 131072
            native_state = ET.fromstring(preferences.read_bytes())
            report["thunar"]["saved_view_state"] = {
                node.get("name"): node.get("value") for node in native_state.findall("./property")
                if node.get("name") in ("last-details-view-column-widths", "last-details-view-zoom-level",
                                         "last-details-view-visible-columns", "last-location-bar", "last-view")}
        if options.reference_only:
            if options.probe_locations:
                assert all(route["passed"] for route in report["thunar"]["native_sidebar_routes"]), report["thunar"]["native_sidebar_routes"]
            report["status"] = "reference-captured"
            return 0
        executable = REPO / "build/shelf-desktop"
        before = digest(executable)
        report["shelf"] = capture("shelf", [executable], path,
                                  options.populated_home, options.probe_locations)
        filesystem.report["after_shelf"] = filesystem.sample()
        assert filesystem.report["fixture_ready"] == filesystem.report["after_shelf"], "Shelf browsing changed fixture filesystem"
        assert digest(executable) == before, "Shelf executable changed during comparison"
        report["shelf"]["sha256"] = before
        report["comparison"] = compare()
        report["state_comparisons"] = {state: compare("-" + state) for state in ("selected", "hover")}
        if options.populated_home:
            report["state_comparisons"]["scrolled"] = compare("-scrolled")
        if options.probe_locations:
            failed_routes = [(app, route) for app in ("thunar", "shelf")
                             for route in report[app]["native_sidebar_routes"] if not route["passed"]]
            assert not failed_routes, ("sidebar did not navigate to native URI", failed_routes)
        parity = all(item["exact_pixel_parity"] for item in
                     [report["comparison"], *report["state_comparisons"].values()])
        report["status"] = "pass" if parity else "differences"
        return 0 if report["status"] == "pass" else 1
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        cleanup_error = None
        try:
            if daemon is not None:
                if daemon.poll() is None:
                    daemon.terminate()
                daemon.wait(timeout=8)
        except Exception as error:
            cleanup_error = error
        try:
            if filesystem is not None:
                filesystem.close()
        except Exception as error:
            cleanup_error = error
        if cleanup_error is not None:
            report["status"] = "error"
            report["teardown_error"] = str(cleanup_error)
        (OUTPUT / "report.json").write_text(json.dumps(report, indent=2) + chr(10))
        print(json.dumps({"status": report["status"], "report": str(OUTPUT / "report.json")}))
        if cleanup_error is not None:
            raise cleanup_error


def main():
    global OUTPUT, WIDTH, HEIGHT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-only", action="store_true")
    parser.add_argument("--populated-home", action="store_true",
                        help="compare a populated synthetic Home at reference-relevant 960x1020")
    parser.add_argument("--probe-locations", action="store_true",
                        help="also verify actual standard-fixture Computer/Recent/Network sidebar navigation")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.populated_home and options.probe_locations:
        parser.error("--probe-locations uses the standard fixture")
    if options.populated_home:
        OUTPUT = OUTPUT / "populated-home"
        WIDTH, HEIGHT = 960, 1020
    if options.worker:
        return worker(options)
    env = prepare(discover())
    screen = f"-screen 0 1280x{max(900, HEIGHT + 40)}x24 -nolisten tcp"
    command = ["unshare", "--user", "--map-current-user", "--keep-caps", "--mount", "--propagation", "private", "dbus-run-session", "--", "xvfb-run", "-a", "-s", screen,
               "/usr/bin/python3", str(Path(__file__).resolve()), "--worker"]
    if options.reference_only:
        command.append("--reference-only")
    if options.populated_home:
        command.append("--populated-home")
    if options.probe_locations:
        command.append("--probe-locations")
    return subprocess.run(command, env=env, timeout=150).returncode


if __name__ == "__main__":
    sys.exit(main())
