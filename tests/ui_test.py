#!/usr/bin/env python3
"""Exercise the owned desktop app and capture its views on a private X server."""
import os
import argparse
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw


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


def main():
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
    destination = fixture / "destination"
    destination.mkdir(parents=True)
    env = os.environ.copy()
    env.update(HOME=str(fixture), XDG_DATA_HOME=str(fixture / "data-home"),
               XDG_CONFIG_HOME=str(fixture / ".config"),
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
        css.write_text("\n".join(f"@define-color {token} #{colors[color]};" for token, color in (
            ("theme_bg_color", "bg"), ("theme_base_color", "base"),
            ("theme_fg_color", "fg"), ("theme_selected_bg_color", "selected"),
            ("theme_selected_fg_color", "selected_fg"), ("borders", "border"))))
    settings = fixture / ".config/gtk-3.0/settings.ini"
    settings.parent.mkdir(parents=True)

    def set_theme(name):
        settings.write_text("[Settings]\ngtk-theme-name=ShelfTest" + name + "\n")

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
            # The File toolbar action's position follows the app's viewport width.
            xdo("mousemove", "--window", window, int(geometry["WIDTH"]) - 229, 26)
            xdo("click", "1")
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

            def navigate(path):
                key("ctrl+l")
                key("ctrl+a")
                xdo("type", "--clearmodifiers", "--delay", "1", str(path))
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

            def entry_point(mode, index):
                if mode == "List":
                    return 200, 184 + index * 32
                if mode == "Icon":
                    across = max(1, (width - 174 - 12 + 4) // 132)
                    cell = (width - 174 - 12 - 4 * (across - 1)) // across
                    return (172 + (index % across) * (cell + 4) + cell // 2,
                            142 + (index // across) * 108 + 52)
                across = max(1, (height - 168 - 12 + 4) // 36)
                cell = (height - 168 - 12 - 4 * (across - 1)) // across
                return (172 + (index // across) * 196 + 96,
                        142 + (index % across) * (cell + 4) + cell // 2)

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
                            center_x, center_y = entry_point(mode, 0)
                            if mode == "Icon":
                                area = (center_x - 24, 146, center_x + 24, 194)
                            elif mode == "Compact":
                                area = (176, center_y - 9, 194, center_y + 9)
                            else:
                                area = (180, 171, width - 30, 196)
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
                    key("Escape", "ctrl+l")
                    with Image.open(capture("theme-" + name.lower() + "-prompt")) as shot:
                        rendered = shot.convert("RGB")
                        left, top = width // 2 - 220, height // 2 - 46
                        assert close(rendered.getpixel((left + 2, top + 2)), base), (name, "prompt surface")
                        assert foreground_count(rendered, (left + 16, top + 12, left + 424, top + 34), fg) > 8, (name, "prompt text")
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

            for mode, shortcut in (("Icon", "ctrl+1"), ("List", "ctrl+2"),
                                   ("Compact", "ctrl+3")):
                navigate(source)
                key(shortcut)
                if mode != "Icon":
                    click(166 + 250 + 30, 112)  # Name, ascending after prior Size sort.
                key("Home")
                subprocess.run(["import", "-window", window,
                                str(repo / "build" / (options.capture_prefix + "-" + mode.lower() + ".png"))],
                               check=True, timeout=10)
                click(*entry_point(mode, 0))
                click(*entry_point(mode, 2), modifier="ctrl")
                click(*entry_point(mode, 3), modifier="shift")
                click(*entry_point(mode, 0), modifier="ctrl+shift")
                click(width - 90, 26)
                pointer_target = fixture / (mode.lower() + "-pointer")
                pointer_target.mkdir()
                navigate(pointer_target)
                click(width - 30, 26)
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
                click(width - 90, 26)  # Copy uses the shared selection.
                target = fixture / (mode.lower() + "-focus")
                target.mkdir()
                navigate(target)
                click(width - 30, 26)
                wait_for(lambda: (target / "file59.txt").is_file(),
                         mode + " keyboard selection copy", process)
                assert sorted(p.name for p in target.iterdir()) == ["00-folder", "file59.txt"], mode
                assert (target / "00-folder" / "nested.txt").read_text() == "nested"

                navigate(source)
                key(shortcut)
                key("Home")
                key("shift+End")
                # Sort/reverse and switch layouts while keeping every identity.
                click(166 + 250 + 78, 112)  # Size, ascending on first use.
                click(166 + 562 + 30, 112)  # Reverse.
                key("ctrl+2", shortcut)
                click(width - 90, 26)
                target = fixture / (mode.lower() + "-range")
                target.mkdir()
                navigate(target)
                click(width - 30, 26)
                wait_for(lambda: len(list(target.iterdir())) == 61,
                         mode + " range across sort and mode switch", process)
                assert sorted(p.name for p in target.iterdir()) == sorted(p.name for p in source.iterdir())

                # Enter opens the directory after Home in every layout.
                navigate(source)
                key(shortcut)
                key("Home", "Return")
                click(width - 229, 26)
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
                click(width - 229, 26)
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


if __name__ == "__main__":
    main()
