#!/usr/bin/env python3
"""Exercise the owned desktop app and capture its views on a private X server."""
import os
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw


def require_private_display(env=None):
    active = os.environ if env is None else env
    assert active.get("YUE_DESKTOP_RECOVERY") == "0", "private desktop recovery must be disabled"
    display = active.get("DISPLAY", "")
    assert display.startswith(":"), "an owned local Xvfb is required"
    number = display[1:].split(".")[0]
    assert number.isdecimal()
    pid = int(Path(f"/tmp/.X{number}-lock").read_text().strip())
    assert Path(f"/proc/{pid}/comm").read_text().strip() == "Xvfb", "refusing a foreign display"


def native_chrome_geometry(env=None):
    """Query real GTK widgets in the same private theme as the tested app."""
    require_private_display(env)
    import json
    import textwrap
    probe = '''
import gi,json
gi.require_version('Gtk','3.0')
from gi.repository import Gtk
w=Gtk.OffscreenWindow();w.get_style_context().add_class('thunar')
g=Gtk.Grid();w.add(g)
m=Gtk.MenuBar();g.attach(m,0,0,1,1)
for title in ('File','Edit','View','Go','Bookmarks','Help'):m.append(Gtk.MenuItem(label=title))
t=Gtk.Toolbar();t.set_style(Gtk.ToolbarStyle.ICONS);t.set_icon_size(Gtk.IconSize.LARGE_TOOLBAR);g.attach(t,0,1,1,1)
b=Gtk.ToolButton();b.set_icon_widget(Gtk.Image.new_from_icon_name('go-up-symbolic',Gtk.IconSize.LARGE_TOOLBAR));t.insert(b,-1)
i=Gtk.ToolItem();i.add(Gtk.Entry());t.insert(i,-1)
p=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL);p.add1(Gtk.Box());p.add2(Gtk.Box());g.attach(p,0,2,1,1)
s=Gtk.Statusbar();s.set_margin_top(0);s.set_margin_bottom(0);s.push(0,'Status');g.attach(s,0,3,1,1)
f=Gtk.ScrolledWindow();f.get_style_context().add_class('standard-view');f.get_style_context().add_class('frame');g.attach(f,0,4,1,1)
v=Gtk.TreeView(model=Gtk.ListStore(str));f.add(v);v.get_model().append(['item'])
c=Gtk.TreeViewColumn('Name');v.append_column(c);c.set_sort_indicator(True)
pix=Gtk.CellRendererPixbuf(icon_name='folder',stock_size=Gtk.IconSize.DIALOG,xpad=1,ypad=1);c.pack_start(pix,False)
text=Gtk.CellRendererText();c.pack_start(text,True);c.add_attribute(text,'text',0)
w.show_all()
while Gtk.events_pending():Gtk.main_iteration_do(False)
a=m.get_allocation();border=f.get_style_context().get_border(Gtk.StateFlags.NORMAL)
r={'menus':{},'menu_height':a.height,'toolbar_height':t.get_allocated_height(),
   'separator_width':p.get_preferred_width()[0],'status_height':s.get_preferred_height()[1],
   'header_height':c.get_button().get_preferred_height()[1],
   'frame_top':border.top,'row_height':v.get_background_area(Gtk.TreePath.new_from_indices([0]),c).height}
for child in m.get_children():
 a=child.get_allocation();r['menus'][child.get_label()]=[a.x,a.width]
print(json.dumps(r));w.destroy()
'''
    result = subprocess.run(['/usr/bin/python3', '-c', textwrap.dedent(probe)],
                            env=env, capture_output=True, text=True, check=True, timeout=15)
    return json.loads(result.stdout)


def native_detail_geometry(directory, width, env=None):
    """Allocate real GTK detail columns from the fixture's native GIO metadata."""
    require_private_display(env)
    import json
    probe = '''
import gi,json,sys
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gio,GLib,Pango
w=Gtk.OffscreenWindow();w.get_style_context().add_class('thunar')
g=Gtk.Grid();w.add(g);f=Gtk.ScrolledWindow();f.set_hexpand(True);f.set_vexpand(True);g.add(f)
f.get_style_context().add_class('frame');f.get_style_context().add_class('standard-view')
m=Gtk.ListStore(str,str,str,str)
for child in Gio.File.new_for_path(sys.argv[1]).enumerate_children('standard::name,standard::size,standard::content-type',Gio.FileQueryInfoFlags.NONE,None):
 m.append([child.get_name(),GLib.format_size_full(child.get_size(),GLib.FormatSizeFlags.IEC_UNITS),Gio.content_type_get_description(child.get_content_type()),'Today'])
v=Gtk.TreeView(model=m);f.add(v);columns=[]
for i,title in enumerate(('Name','Size','Type','Date Modified')):
 c=Gtk.TreeViewColumn();c.set_title(title);c.set_min_width(50);c.set_resizable(True);c.set_sort_column_id(i);c.set_sizing(Gtk.TreeViewColumnSizing.GROW_ONLY)
 if i==0:
  c.pack_start(Gtk.CellRendererPixbuf(icon_name='folder',stock_size=Gtk.IconSize.DIALOG,xpad=1,ypad=1),False)
  cell=Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.END,width_chars=60);c.set_expand(True)
 else:cell=Gtk.CellRendererText(xalign=1 if i==1 else 0)
 c.pack_start(cell,True);c.add_attribute(cell,'text',i);v.append_column(c);columns.append(c)
columns[0].set_sort_indicator(True);w.set_default_size(int(sys.argv[2]),240);w.show_all()
while Gtk.events_pending():Gtk.main_iteration_do(False)
left=0;r={}
for c in columns:r[c.get_title()]=left+c.get_width()//2;left+=c.get_width()
print(json.dumps(r));w.destroy()
'''
    result = subprocess.run(['/usr/bin/python3', '-c', probe, str(directory), str(width)],
                            env=env, capture_output=True, text=True, check=True, timeout=15)
    return json.loads(result.stdout)


def menu_action(xdo, window, menu, item=None, native_env=None):
    """Use the visible menu bar and native popup rows on the owned window."""
    native = native_chrome_geometry(native_env)
    left, menu_width = native["menus"][menu]
    menu_height = native["menu_height"]
    xdo("mousemove", "--window", window, left + menu_width // 2, menu_height // 2)
    xdo("click", "1")
    time.sleep(.2)
    if item is not None:
        xdo("key", "--window", window, "Home")
        for _ in range(item):
            xdo("key", "--window", window, "Down")
        xdo("key", "--window", window, "Return")
        time.sleep(.2)


def wait_for(check, label, process):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"Shelf exited during {label}: {process.returncode}")
        result = check()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {label}")


def xdo(*args):
    return subprocess.run(["xdotool", *map(str, args)], text=True,
                          capture_output=True, check=True).stdout.strip()




def native_sidebar_geometry():
    """Measure native Thunar cell renderers in the current private GTK theme."""
    probe = r'''import gi, json
 gi.require_version("Gtk", "3.0")
 from gi.repository import Gtk, Pango
 window = Gtk.Window()
 window.get_style_context().add_class("thunar")
 box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
 window.add(box)
 menu = Gtk.MenuBar()
 for title in ("File", "Edit", "View", "Go", "Bookmarks", "Help"):
     menu.append(Gtk.MenuItem(label=title))
 box.pack_start(menu, False, False, 0)
 toolbar = Gtk.Toolbar()
 toolbar.set_icon_size(Gtk.IconSize.LARGE_TOOLBAR)
 button = Gtk.ToolButton()
 button.set_icon_widget(Gtk.Image.new_from_icon_name("go-up-symbolic", Gtk.IconSize.LARGE_TOOLBAR))
 toolbar.insert(button, -1)
 item = Gtk.ToolItem()
 item.add(Gtk.Entry())
 toolbar.insert(item, -1)
 box.pack_start(toolbar, False, False, 0)
 scroller = Gtk.ScrolledWindow()
 scroller.get_style_context().add_class("sidebar")
 scroller.get_style_context().add_class("shortcuts-pane")
 box.pack_start(scroller, True, True, 0)
 model = Gtk.ListStore(bool, str)
 for heading, label in ((True,"Places"),(False,"Computer"),(False,"Home"),
                        (False,"Recent"),(False,"Trash"),(False,"Bookmark 1"),
                        (False,"Bookmark 2"),(True,"Devices"),(False,"File System")):
     model.append((heading,label))
 tree = Gtk.TreeView(model=model)
 tree.set_headers_visible(False)
 scroller.add(tree)
 column = Gtk.TreeViewColumn()
 column.set_spacing(2)
 indent = Gtk.CellRendererText(text="", xpad=6)
 icon = Gtk.CellRendererPixbuf(icon_name="folder", stock_size=Gtk.IconSize.LARGE_TOOLBAR, xpad=0, ypad=0)
 text = Gtk.CellRendererText()
 column.pack_start(indent, False)
 column.pack_start(icon, False)
 column.pack_start(text, True)
 def cell(_column, renderer, model, iterator, _data):
     heading, label = model[iterator]
     if renderer == text:
         renderer.set_properties(text=label, weight=Pango.Weight.BOLD if heading else Pango.Weight.NORMAL,
                                 xpad=6 if heading else 2, ypad=4 if heading else 2)
     else:
         renderer.set_property("visible", not heading)
 for renderer in (indent,icon,text):
     column.set_cell_data_func(renderer, cell, None)
 tree.append_column(column)
 window.set_default_size(640,480)
 window.show_all()
 while Gtk.events_pending(): Gtk.main_iteration_do(False)
 origin = tree.translate_coordinates(window,0,0)
 areas = [tree.get_background_area(Gtk.TreePath.new_from_indices([i]),column) for i in range(len(model))]
 result = {"heading_height":areas[0].height,"row_height":areas[1].height,
           "vertical_separator":tree.style_get_property("vertical-separator"),
           "horizontal_separator":tree.style_get_property("horizontal-separator"),
           "tree_origin":list(origin),
           "bookmark_centers":[origin[1]+areas[i].y+areas[i].height//2 for i in (5,6)]}
 assert result["heading_height"]>0 and result["row_height"]>0
 assert result["bookmark_centers"][1]-result["bookmark_centers"][0]==result["row_height"]
 print(json.dumps(result))
 window.destroy()
'''
    import json
    # Keep GTK/GI in its system interpreter; the test runner may use another Python.
    probe = "\n".join(line[1:] if line.startswith(" ") else line for line in probe.splitlines())
    result = subprocess.run(["/usr/bin/python3", "-c", probe], check=True,
                            capture_output=True, text=True, timeout=15)
    return json.loads(result.stdout)


def assert_editor_text(xdo, expected, process=None):
    """Read actual native clipboard text; fast typing must retain every byte."""
    expected = os.fsencode(expected)
    deadline = time.monotonic() + 6
    actual = b""
    while time.monotonic() < deadline:
        if process is not None:
            assert process.poll() is None, "Shelf exited while checking typed input"
        xdo("key", "--clearmodifiers", "ctrl+a", "ctrl+c")
        read = subprocess.run([sys.executable, str(Path(__file__).with_name("file_clipboard_test.py")),
                               "--read", "UTF8_STRING"], capture_output=True, timeout=10)
        actual = read.stdout
        if read.returncode == 0 and actual == expected:
            return
        time.sleep(.1)
    raise AssertionError(f"Typed location lost or reordered bytes: expected {expected!r}, actual {actual!r}")


def main():
    require_private_display()
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, default=repo / "build/shelf-desktop")
    parser.add_argument("--capture-prefix", default="ui")
    parser.add_argument("--system-theme-config", type=Path)
    parser.add_argument("--system-theme-css", type=Path)
    parser.add_argument("--expected-palette", nargs=3, metavar=("BACKGROUND", "BASE", "TEXT"))
    options = parser.parse_args()
    if any((options.system_theme_config, options.system_theme_css, options.expected_palette)) and not all(
            (options.system_theme_config, options.system_theme_css, options.expected_palette)):
        parser.error("system theme smoke needs config, CSS and the expected RGB palette")
    fixture = repo / "build/ui-test-fixture"
    shutil.rmtree(fixture, ignore_errors=True)
    fixture.mkdir(mode=0o700)
    for folder in ("data-home", ".config", ".cache", ".state"):
        (fixture / folder).mkdir(mode=0o700)
    destination = fixture / "destination"
    destination.mkdir(parents=True)
    env = os.environ.copy()
    env.update(HOME=str(fixture), XDG_DATA_HOME=str(fixture / "data-home"),
               XDG_CONFIG_HOME=str(fixture / ".config"),
               XDG_CACHE_HOME=str(fixture / ".cache"),
               XDG_STATE_HOME=str(fixture / ".state"),
               YUE_DESKTOP_RECOVERY="0", SDL_VIDEODRIVER="x11")
    env.pop("GTK_THEME", None)
    theme_colors = {
        "Light": {"bg": "f6faf8", "base": "e4e9e7", "fg": "191c1b",
                  "selected": "386baf", "selected_fg": "ffffff", "border": "737d79"},
        "Dark": {"bg": "20242c", "base": "151922", "fg": "eef1f5",
                 "selected": "376aaf", "selected_fg": "ffffff", "border": "586274"},
    }
    for name, colors in theme_colors.items():
        css = fixture / ".themes" / ("ShelfTest" + name) / "gtk-3.0/gtk.css"
        css.parent.mkdir(parents=True)
        definitions = "\n".join(f"@define-color {token} #{colors[color]};" for token, color in (
            ("theme_bg_color", "bg"), ("theme_base_color", "base"),
            ("theme_fg_color", "fg"), ("theme_selected_bg_color", "selected"),
            ("theme_selected_fg_color", "selected_fg"), ("borders", "border")))
        # Standalone native GTK themes need selectors as well as named colors.
        # Keep the expected palette assertions; exercise real GTK style loading.
        css.write_text(definitions + "\n" + """
* { color: @theme_fg_color; }
.background, toolbar, menubar, statusbar { background-color: @theme_bg_color; }
.view, iconview, entry { background-color: @theme_base_color; }
.view:selected, iconview:selected { background-color: @theme_selected_bg_color;
                                  color: @theme_selected_fg_color; }
""")
    settings = fixture / ".config/gtk-3.0/settings.ini"
    settings.parent.mkdir(parents=True)
    settings_daemon = None

    def set_theme(name):
        theme = "ShelfTest" + name
        settings.write_text("[Settings]\ngtk-theme-name=" + theme + "\n")
        if settings_daemon is not None:
            assert settings_daemon.poll() is None, "private XSettings manager exited"
            subprocess.run(["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName",
                            "-s", theme], env=env, check=True, capture_output=True, timeout=10)

    set_theme("Light")
    if options.system_theme_config:
        with options.system_theme_config.open("rb") as config:
            contents = config.read(131073)
        assert len(contents) <= 131072, "Theme settings exceed the smoke fixture limit"
        properties = ET.fromstring(contents).iter("property")
        name = next(item.get("value") for item in properties if item.get("name") == "ThemeName")
        assert name and Path(name).name == name and name not in (".", "..")
        copied_config = fixture / ".config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml"
        copied_config.parent.mkdir(parents=True)
        copied_config.write_bytes(contents)
        copied_css = fixture / ".themes" / name / "gtk-3.0/gtk.css"
        copied_css.parent.mkdir(parents=True)
        shutil.copyfile(options.system_theme_css, copied_css)
    opened_path = fixture / "opened-uri.txt"
    env["KRYON_TEST_OPEN_URI_CAPTURE"] = str(opened_path)
    assert env.get("DISPLAY"), "Run through make test-ui on its private Xvfb"
    log_path = repo / "build/ui-test.log"
    with log_path.open("wb") as log:
        # GTK reads settings.ini at startup. Live changes arrive through the
        # private display's XSettings owner, just as they do on XFCE.
        settings_daemon = subprocess.Popen(["xfsettingsd", "--no-daemon"], env=env,
                                           stdout=log, stderr=subprocess.STDOUT)
        time.sleep(.7)
        assert settings_daemon.poll() is None, "private XSettings manager exited"
        if not options.system_theme_config:
            subprocess.run(["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName",
                            "--create", "-t", "string", "-s", "ShelfTestLight"],
                           env=env, check=True, capture_output=True, timeout=10)
        process = subprocess.Popen([str(options.executable)], env=env, cwd=fixture,
                                   stdout=log, stderr=subprocess.STDOUT)
        try:
            def find_window():
                result = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid",
                                         str(process.pid)], text=True, capture_output=True)
                return result.stdout.splitlines()[0] if result.returncode == 0 else None

            window = wait_for(find_window, "owned desktop window", process)
            xdo("windowfocus", "--sync", window)
            xdo("key", "--clearmodifiers", "ctrl+l")
            time.sleep(0.2)
            xdo("key", "--clearmodifiers", "ctrl+a")
            xdo("type", "--clearmodifiers", "--delay", "4", str(destination))
            xdo("key", "Return")
            time.sleep(0.3)
            geometry = dict(line.split("=", 1) for line in
                            xdo("getwindowgeometry", "--shell", window).splitlines())
            menu_action(xdo, window, "File", 1, native_env=env)
            time.sleep(0.2)
            xdo("type", "--clearmodifiers", "--delay", "25", "created-through-ui.txt")
            xdo("key", "Return")
            wait_for(lambda: (destination / "created-through-ui.txt").is_file(),
                     "file creation in the navigated directory", process)
            assert not (fixture / "created-through-ui.txt").exists()
            def key(*keys):
                for item in keys:
                    xdo("key", "--clearmodifiers", item)
                    time.sleep(0.12)

            def click(x, y, modifier=None):
                xdo("mousemove", "--window", window, x, y)
                if modifier:
                    xdo("keydown", modifier)
                xdo("click", "1")
                if modifier:
                    xdo("keyup", modifier)
                time.sleep(0.15)

            def navigate(path, verify_editor=True):
                key("ctrl+l")
                key("ctrl+a")
                xdo("type", "--clearmodifiers", "--delay", "1", str(path))
                # Ctrl+C is the exact-byte typing oracle. Keep it outside a
                # pending file transfer: copying editor text replaces the real
                # native file clipboard, just as it does in an ordinary app.
                if verify_editor:
                    assert_editor_text(xdo, str(path), process)
                key("Return")
                time.sleep(0.2)

            def capture(name):
                path = repo / "build" / (options.capture_prefix + "-" + name + ".png")
                subprocess.run(["import", "-window", window, str(path)], check=True, timeout=10)
                return path

            def preview_tests():
                previews = fixture / "previews"
                previews.mkdir(exist_ok=True)
                picture = Image.new("RGB", (1600, 1000), (230, 25, 35))
                draw = ImageDraw.Draw(picture)
                draw.rectangle((800, 0, 1599, 999), fill=(25, 45, 230))
                formats = (("01-picture.png", "PNG"), ("02-picture.jpg", "JPEG"),
                           ("03-picture.webp", "WEBP"), ("04-picture.gif", "GIF"),
                           ("05-picture.bmp", "BMP"), ("06-picture.tiff", "TIFF"))
                for filename, encoding in formats:
                    picture.save(previews / filename, format=encoding)
                (previews / "07-picture.svg").write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000">'
                    '<rect width="800" height="1000" fill="#e61923"/>'
                    '<rect x="800" width="800" height="1000" fill="#192de6"/></svg>')
                (previews / "08-broken.png").write_bytes(b"not a picture")
                (previews / "09-notes.txt").write_text("Hello é 世界\n" + "preview text\n" * 200)
                (previews / "10-binary.bin").write_bytes(b"binary\0contents")
                (previews / "11-long.txt").write_text("long line\n" * 10000)
                picture.save(previews / "12-image-without-extension", format="PNG")
                alpha = Image.new("RGBA", (1600, 1000), (0, 0, 0, 0))
                alpha_draw = ImageDraw.Draw(alpha)
                alpha_draw.rectangle((0, 0, 699, 999), fill=(230, 25, 35, 255))
                alpha_draw.rectangle((900, 0, 1599, 999), fill=(25, 45, 230, 255))
                alpha.save(previews / "13-alpha.png")
                navigate(previews)
                key("ctrl+1", "Home")
                capture("thumbnails")
                key("Return")
                for index, extension in enumerate(("png", "jpg", "webp", "gif", "bmp", "tiff", "svg")):
                    time.sleep(0.25)
                    shot = capture("preview-" + extension)
                    with Image.open(shot) as rendered:
                        body = rendered.convert("RGB").crop((16, 90, width - 16, height - 72))
                        colors = body.tobytes()
                    red = sum(colors[at] > 180 and colors[at + 1] < 100 and colors[at + 2] < 100
                              for at in range(0, len(colors), 3))
                    blue = sum(colors[at + 2] > 180 and colors[at] < 100 and colors[at + 1] < 100
                               for at in range(0, len(colors), 3))
                    assert red > 10000 and blue > 10000, (extension, red, blue)
                    if index < 6:
                        key("Next")
                # Zoom and source panning must keep a real image on screen.
                key("0", "plus", "Right", "Down")
                capture("preview-zoom")
                key("Home", "Return")
                wait_for(lambda: opened_path.exists() and opened_path.read_text() == str(previews / "07-picture.svg"),
                         "preview Open preserves exact file path", process)
                key("Next")
                capture("preview-unavailable")
                # Escape restores the same focused file and the file-list keys.
                key("Escape", "ctrl+2", "Down", "ctrl+p", "End")
                capture("preview-text")
                key("Escape", "Return")
                wait_for(lambda: opened_path.read_text() == str(previews / "09-notes.txt"),
                         "ordinary file activation opens default application", process)
                key("Down", "ctrl+p")
                capture("preview-binary")
                key("Escape", "Down", "ctrl+p")
                capture("preview-limited-text")
                key("Escape")
                key("Down", "Return")
                capture("preview-no-extension")
                key("Return")
                wait_for(lambda: opened_path.read_text() == str(previews / "12-image-without-extension"),
                         "image content detection without extension", process)
                key("Escape", "Down", "Return")
                alpha_shot = capture("preview-alpha")
                with Image.open(alpha_shot) as rendered:
                    center = rendered.convert("RGB").getpixel((width // 2, 160))
                assert all(abs(a - b) <= 3 for a, b in zip(center, (228, 233, 231))), center
                key("Escape")

            width = int(geometry["WIDTH"])
            height = int(geometry["HEIGHT"])

            native = native_chrome_geometry(env)
            chrome = native["menu_height"] + native["toolbar_height"]
            pane_left = 170 + native["separator_width"]
            pane_width = width - pane_left
            pane_height = height - chrome - native["status_height"]

            def entry_point(mode, index):
                if mode == "List":
                    return pane_left + 80, (chrome + native["frame_top"] +
                        native["header_height"] + native["row_height"] // 2 +
                        index * native["row_height"])
                if mode == "Icon":
                    across = max(1, (pane_width - 12 + 4) // 132)
                    cell = (pane_width - 12 - 4 * (across - 1)) // across
                    return (pane_left + 6 + (index % across) * (cell + 4) + cell // 2,
                            chrome + 6 + (index // across) * 108 + 52)
                across = max(1, (pane_height - 12 + 4) // 36)
                cell = (pane_height - 12 - 4 * (across - 1)) // across
                return (pane_left + 6 + (index // across) * 196 + 96,
                        chrome + 6 + (index % across) * (cell + 4) + cell // 2)

            def theme_tests(system=False):
                themed = fixture / "theme-files"
                themed.mkdir()
                for index in range(3):
                    (themed / f"note{index}.txt").write_text("Readable themed text\n")
                alpha_only = fixture / "theme-alpha"
                alpha_only.mkdir()
                Image.new("RGBA", (1600, 1000), (0, 0, 0, 0)).save(alpha_only / "alpha.png")

                def rgb(value):
                    return tuple(bytes.fromhex(value))

                def close(actual, expected):
                    return all(abs(a - b) <= 3 for a, b in zip(actual, expected))

                def foreground_count(rendered, area, fg):
                    pixels = rendered.crop(area).tobytes()
                    return sum(close(pixels[at:at + 3], fg) for at in range(0, len(pixels), 3))

                for name in (("System",) if system else ("Dark", "Light")):
                    if system:
                        colors = dict(zip(("bg", "base", "fg"), options.expected_palette))
                    else:
                        set_theme(name)
                        time.sleep(1.1)
                        colors = theme_colors[name]
                    bg, base, fg = (rgb(colors[key]) for key in ("bg", "base", "fg"))
                    for mode, shortcut in (("Icon", "ctrl+1"), ("List", "ctrl+2"),
                                           ("Compact", "ctrl+3")):
                        navigate(themed)
                        key(shortcut, "Home")
                        xdo("mousemove", "--window", window, 2, 2)
                        with Image.open(capture("theme-" + name.lower() + "-" + mode.lower())) as shot:
                            rendered = shot.convert("RGB")
                            assert close(rendered.getpixel((width - 2, height - 2)), bg), (name, mode, "canvas")
                            # Empty table space uses the semantic surface rather than a fixed light face.
                            if mode == "List":
                                assert close(rendered.getpixel((width - 30, height - 90)), base), (name, "table surface")
                            # The second row is unselected: verify the configured
                            # normal foreground independently of selection colors.
                            center_x, center_y = entry_point(mode, 1)
                            if mode == "Icon":
                                area = (center_x - 60, center_y + 4, center_x + 60, center_y + 48)
                            elif mode == "Compact":
                                area = (202, center_y - 12, 350, center_y + 12)
                            else:
                                area = (224, center_y - 15, width - 30, center_y + 15)
                            foreground = foreground_count(rendered, area, fg)
                            assert foreground > 8, (name, mode, "readable glyphs", foreground)
                    navigate(alpha_only)
                    key("ctrl+2", "Home", "Return")
                    with Image.open(capture("theme-" + name.lower() + "-alpha")) as shot:
                        rendered = shot.convert("RGB")
                        assert close(rendered.getpixel((width // 2, 160)), base), (name, "transparent preview")
                        assert close(rendered.getpixel((width - 2, height - 2)), bg), (name, "preview canvas")
                    key("Escape")
                    navigate(themed)
                    key("Home", "ctrl+p")
                    with Image.open(capture("theme-" + name.lower() + "-text")) as shot:
                        rendered = shot.convert("RGB")
                        assert foreground_count(rendered, (12, 80, width // 2, 110), fg) > 8, (name, "preview text")
                    key("Escape", "ctrl+l", "End")
                    with Image.open(capture("theme-" + name.lower() + "-prompt")) as shot:
                        rendered = shot.convert("RGB")
                        # Ctrl+L now edits inline; both path and native completion
                        # hint must follow the same configured theme.
                        left, top = 150, 32
                        right = width - 46
                        assert close(rendered.getpixel((width - 10, height - 5)), bg), (name, "location status surface")
                        assert foreground_count(rendered, (left + 8, top + 2, right - 8, top + 24), fg) > 8, (name, "location text")
                        assert foreground_count(rendered, (166, height - 26, width - 8, height - 4), fg) > 8, (name, "location status hint")
                    key("Escape")
            if options.system_theme_config:
                theme_tests(system=True)
                print("Shelf installed private-Xvfb current system theme: all three views, glyphs, table, preview and prompt local tests passed")
                return
            source = fixture / "view-source"
            source.mkdir()
            (source / "00-folder").mkdir()
            (source / "00-folder" / "nested.txt").write_text("nested")
            for index in range(60):
                (source / f"file{index:02}.txt").write_text("x" * (index + 1))

            detail_headers = native_detail_geometry(source, pane_width, env)
            for mode, shortcut in (("Icon", "ctrl+1"), ("List", "ctrl+2"),
                                   ("Compact", "ctrl+3")):
                navigate(source)
                key(shortcut)
                if mode != "Icon":
                    key("ctrl+2")
                    click(pane_left + 80, chrome + native["frame_top"] + native["header_height"] // 2)  # Name sort.
                    key(shortcut)
                key("Home")
                subprocess.run(["import", "-window", window,
                                str(repo / "build" / (options.capture_prefix + "-" + mode.lower() + ".png"))],
                               check=True, timeout=10)
                click(*entry_point(mode, 0))
                click(*entry_point(mode, 2), modifier="ctrl")
                click(*entry_point(mode, 3), modifier="shift")
                click(*entry_point(mode, 0), modifier="ctrl+shift")
                menu_action(xdo, window, "Edit", 3, native_env=env)
                pointer_target = fixture / (mode.lower() + "-pointer")
                pointer_target.mkdir()
                navigate(pointer_target, verify_editor=False)
                menu_action(xdo, window, "Edit", 4, native_env=env)
                wait_for(lambda: len(list(pointer_target.iterdir())) == 4,
                         mode + " pointer multi-selection", process)
                assert sorted(p.name for p in pointer_target.iterdir()) == [
                    "00-folder", "file00.txt", "file01.txt", "file02.txt"], mode

                navigate(source)
                key(shortcut, "Home")
                # Keep the folder selected while focus travels to the last item.
                key("ctrl+End")
                xdo("mousemove", "--window", window, width - 100, height - 100)
                xdo("click", "--repeat", "2", "--delay", "30", "4")
                key("space")
                menu_action(xdo, window, "Edit", 3, native_env=env)  # Copy uses the shared selection.
                target = fixture / (mode.lower() + "-focus")
                target.mkdir()
                navigate(target, verify_editor=False)
                menu_action(xdo, window, "Edit", 4, native_env=env)
                wait_for(lambda: (target / "file59.txt").is_file(),
                         mode + " keyboard selection copy", process)
                assert sorted(p.name for p in target.iterdir()) == ["00-folder", "file59.txt"], mode
                assert (target / "00-folder" / "nested.txt").read_text() == "nested"

                navigate(source)
                key(shortcut)
                key("Home")
                key("shift+End")
                # Sort/reverse and switch layouts while keeping every identity.
                key("ctrl+2")
                click(pane_left + detail_headers["Size"], chrome + native["frame_top"] + native["header_height"] // 2)  # Size, ascending on first use.
                click(pane_left + detail_headers["Size"], chrome + native["frame_top"] + native["header_height"] // 2)  # Reverse the same sort column.
                key("ctrl+2", shortcut)
                menu_action(xdo, window, "Edit", 3, native_env=env)
                target = fixture / (mode.lower() + "-range")
                target.mkdir()
                navigate(target, verify_editor=False)
                menu_action(xdo, window, "Edit", 4, native_env=env)
                wait_for(lambda: len(list(target.iterdir())) == 61,
                         mode + " range across sort and mode switch", process)
                assert sorted(p.name for p in target.iterdir()) == sorted(p.name for p in source.iterdir())

                # Enter opens the directory after Home in every layout.
                navigate(source)
                key(shortcut)
                key("Home", "Return")
                menu_action(xdo, window, "File", 1, native_env=env)
                xdo("type", "--clearmodifiers", "--delay", "3", mode.lower() + "-entered.txt")
                key("Return")
                wait_for(lambda: (source / "00-folder" / (mode.lower() + "-entered.txt")).is_file(),
                         mode + " activation", process)
            # Reopen only the executable this private test owns, then exercise
            # every layout again against the same filesystem fixture.
            process.terminate()
            process.wait(timeout=10)
            process = subprocess.Popen([str(options.executable)], env=env, cwd=fixture,
                                       stdout=log, stderr=subprocess.STDOUT)
            window = wait_for(find_window, "reopened owned desktop window", process)
            xdo("windowfocus", "--sync", window)
            preview_tests()
            theme_tests()
            for mode, shortcut in (("Icon", "ctrl+1"), ("List", "ctrl+2"),
                                   ("Compact", "ctrl+3")):
                navigate(source)
                key(shortcut, "Home", "Return")
                menu_action(xdo, window, "File", 1, native_env=env)
                name = mode.lower() + "-reopened.txt"
                xdo("type", "--clearmodifiers", "--delay", "3", name)
                key("Return")
                wait_for(lambda: (source / "00-folder" / name).is_file(),
                         mode + " after desktop close/reopen", process)
            print("Shelf private-Xvfb three-view selection, sorting, image/text preview, system light/dark/live theme changes, opening and reopen local tests passed")
        except Exception:
            if "window" in locals() and shutil.which("import"):
                subprocess.run(["import", "-window", window,
                                str(repo / "build" / (options.capture_prefix + "-test.png"))],
                               check=False, timeout=10)
            raise
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
            if settings_daemon.poll() is None:
                settings_daemon.terminate()
            settings_daemon.wait(timeout=10)


if __name__ == "__main__":
    main()
