#!/usr/bin/env python3
"""Read the installed Thunar's real context menus on a private desktop.

Run inside tests/private_desktop.py. Thunar runs against a private copy of
the owner's Thunar, MIME and application settings; the menus are read through
AT-SPI, exactly as GTK exposes them, and each popup is captured from the
private Xvfb root window only. Writes build/context-menu/thunar.json.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/context-menu"


def private_settings(home):
    """Copy only the bounded owner files that select menu contents."""
    owner = Path(os.path.expanduser("~" + os.environ.get("EXPLORER_OWNER", "")))
    if os.environ.get("EXPLORER_OWNER_HOME"):
        owner = Path(os.environ["EXPLORER_OWNER_HOME"])
    config = Path(os.environ["XDG_CONFIG_HOME"])
    data = Path(os.environ["XDG_DATA_HOME"])
    copied = []
    for source, target in ((owner / ".config/Thunar/uca.xml", config / "Thunar/uca.xml"),
                           (owner / ".config/Thunar/accels.scm", config / "Thunar/accels.scm"),
                           (owner / ".config/mimeapps.list", config / "mimeapps.list"),
                           (owner / ".config/xfce4/xfconf/xfce-perchannel-xml/thunar.xml",
                            config / "xfce4/xfconf/xfce-perchannel-xml/thunar.xml")):
        if source.is_file() and source.stat().st_size <= 1048576:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(str(target))
    applications = owner / ".local/share/applications"
    if applications.is_dir():
        target = data / "applications"
        target.mkdir(parents=True, exist_ok=True)
        for item in applications.iterdir():
            if item.suffix == ".desktop" and item.is_file() and item.stat().st_size <= 262144:
                shutil.copyfile(item, target / item.name)
        copied.append(str(target))
    return copied


def fixture(home):
    from PIL import Image
    path = home / "Fixture"
    path.mkdir()
    (path / "01 Folder").mkdir()
    (path / "01 Folder/inside.txt").write_text("inside\n")
    (path / "02 Empty").mkdir()
    (path / "04 Notes.txt").write_text("Explorer and Thunar context menu comparison.\n")
    Image.new("RGB", (64, 64), (30, 120, 210)).save(path / "05 Image.png")
    subprocess.run(["zip", "-q", "-j", str(path / "06 Archive.zip"), str(path / "04 Notes.txt")], check=False)
    script = path / "07 Script.sh"
    script.write_text("#!/bin/sh\necho test\n")
    script.chmod(0o755)
    (path / "08 Link.txt").symlink_to("04 Notes.txt")
    for item in path.iterdir():
        os.utime(item, (1700000000, 1700000000), follow_symlinks=False)
    desktop = home / "Desktop"
    desktop.mkdir(exist_ok=True)
    config = Path(os.environ["XDG_CONFIG_HOME"])
    (config / "user-dirs.dirs").write_text(f'XDG_DESKTOP_DIR="{desktop}"\n')
    bookmarks = config / "gtk-3.0/bookmarks"
    bookmarks.parent.mkdir(parents=True, exist_ok=True)
    bookmarks.write_text((path / "01 Folder").as_uri() + " Bookmarked Folder\n")
    return path


def atspi():
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    return Atspi


def application(Atspi, pid, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        desktop = Atspi.get_desktop(0)
        for index in range(desktop.get_child_count()):
            app = desktop.get_child_at_index(index)
            try:
                if app is not None and app.get_process_id() == pid:
                    return app
            except Exception:
                pass
        time.sleep(.2)
    raise AssertionError("Thunar is not visible through AT-SPI")


def walk(node, depth=0):
    if node is None or depth > 40:
        return
    yield node
    try:
        count = node.get_child_count()
    except Exception:
        return
    for index in range(count):
        try:
            child = node.get_child_at_index(index)
        except Exception:
            continue
        yield from walk(child, depth + 1)


MENU_ROLES = {"menu item", "check menu item", "radio menu item", "menu", "separator", "tearoff menu item"}


def entry(Atspi, node):
    role = node.get_role_name()
    states = node.get_state_set()
    if not states.contains(Atspi.StateType.VISIBLE):
        return None
    result = {"label": node.get_name() or "", "sensitive": states.contains(Atspi.StateType.SENSITIVE)}
    if role == "separator":
        return {"separator": True}
    binding = ""
    try:
        action = node.get_action_iface()
        if action is not None and action.get_n_actions() > 0:
            binding = action.get_key_binding(0) or ""
    except Exception:
        pass
    fields = binding.split(";")
    result["accelerator"] = fields[2] if len(fields) > 2 else ""
    if role in ("check menu item", "radio menu item"):
        result["kind"] = "radio" if role == "radio menu item" else "check"
        result["checked"] = states.contains(Atspi.StateType.CHECKED)
    if role == "menu":
        result["submenu"] = menu_entries(Atspi, node)
    return result


def menu_entries(Atspi, menu):
    items = []
    for index in range(menu.get_child_count()):
        child = menu.get_child_at_index(index)
        if child is None or child.get_role_name() not in MENU_ROLES:
            continue
        value = entry(Atspi, child)
        if value is not None:
            items.append(value)
    # Every visible separator is drawn, adjacent or trailing ones included.
    return items


def popup(Atspi, app, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for index in range(app.get_child_count()):
            node = app.get_child_at_index(index)
            try:
                if node is None or node.get_role_name() != "window":
                    continue
                if not node.get_state_set().contains(Atspi.StateType.SHOWING):
                    continue
                for index in range(node.get_child_count()):
                    child = node.get_child_at_index(index)
                    if child is not None and child.get_role_name() == "menu" and \
                            child.get_state_set().contains(Atspi.StateType.SHOWING):
                        return child
            except Exception:
                continue
        time.sleep(.1)
    raise AssertionError("Thunar context menu did not open")


def extents(Atspi, node):
    box = node.get_extents(Atspi.CoordType.SCREEN)
    return box.x, box.y, box.width, box.height


TABLES = []


def find_cell(Atspi, app, name, table_index):
    if not TABLES:
        TABLES.extend(node for node in walk(app) if node.get_role_name() in ("tree table", "table"))
        TABLES.sort(key=lambda node: extents(Atspi, node)[0])
    table = TABLES[table_index]
    # Icon+text columns expose a container cell whose child carries the name.
    for index in range(table.get_child_count()):
        node = table.get_child_at_index(index)
        if node is None or node.get_role_name() != "table cell":
            continue
        if node.get_name() == name:
            return node, table
        for inner in range(node.get_child_count()):
            child = node.get_child_at_index(inner)
            if child is not None and child.get_name() == name:
                return child, table
    raise AssertionError(f"missing row {name!r}")


def xdotool(*args):
    subprocess.run(["xdotool", *map(str, args)], check=True)


def capture(name):
    subprocess.run(["import", "-window", "root", str(OUTPUT / f"thunar-{name}.png")], check=False)


def close_menu():
    xdotool("key", "Escape")
    time.sleep(.3)


def click(Atspi, node, button=1, modifier=None):
    x, y, width, height = extents(Atspi, node)
    xdotool("mousemove", "--sync", x + min(width // 2, 40), y + height // 2)
    if modifier:
        xdotool("keydown", modifier)
    xdotool("click", button)
    if modifier:
        xdotool("keyup", modifier)
    time.sleep(.4)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    home = Path(os.environ["HOME"])
    copied = private_settings(home)
    folder = fixture(home)
    Atspi = atspi()
    env = os.environ.copy()
    env.pop("NO_AT_BRIDGE", None)
    env.update(GDK_BACKEND="x11", LC_ALL=os.environ.get("EXPLORER_MENU_LOCALE", "C.UTF-8"))
    thunar = subprocess.Popen(["/usr/bin/thunar", str(folder)], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    report = {"thunar": subprocess.run(["/usr/bin/thunar", "--version"], capture_output=True,
                                       text=True).stdout.splitlines()[0],
              "settings": copied, "fixture": str(folder), "menus": {}}
    try:
        app = application(Atspi, thunar.pid)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            windows = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(thunar.pid)],
                                     capture_output=True, text=True).stdout.split()
            if windows:
                break
            time.sleep(.2)
        assert windows, "Thunar window missing"
        xdotool("windowsize", "--sync", windows[0], 1000, 760)
        xdotool("windowfocus", "--sync", windows[0])
        time.sleep(1.5)

        def record(name, open_menu):
            open_menu()
            menu = popup(Atspi, app)
            time.sleep(.3)
            capture(name)
            report["menus"][name] = menu_entries(Atspi, menu)
            close_menu()
            (OUTPUT / "thunar.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")

        def row(name, table=1):
            return find_cell(Atspi, app, name, table)[0]

        record("file", lambda: (click(Atspi, row("04 Notes.txt")), click(Atspi, row("04 Notes.txt"), 3)))
        record("image", lambda: (click(Atspi, row("05 Image.png")), click(Atspi, row("05 Image.png"), 3)))
        record("archive", lambda: (click(Atspi, row("06 Archive.zip")), click(Atspi, row("06 Archive.zip"), 3)))
        record("executable", lambda: (click(Atspi, row("07 Script.sh")), click(Atspi, row("07 Script.sh"), 3)))
        record("link", lambda: (click(Atspi, row("08 Link.txt")), click(Atspi, row("08 Link.txt"), 3)))
        record("multiple", lambda: (click(Atspi, row("04 Notes.txt")),
                                    click(Atspi, row("05 Image.png"), 1, "ctrl"),
                                    click(Atspi, row("05 Image.png"), 3)))
        record("mixed", lambda: (click(Atspi, row("01 Folder")),
                                 click(Atspi, row("04 Notes.txt"), 1, "ctrl"),
                                 click(Atspi, row("04 Notes.txt"), 3)))
        record("folder", lambda: (click(Atspi, row("01 Folder")), click(Atspi, row("01 Folder"), 3)))

        def background():
            _, table = find_cell(Atspi, app, "04 Notes.txt", 1)
            x, y, width, height = extents(Atspi, table)
            xdotool("mousemove", "--sync", x + width // 2, y + height - 20)
            xdotool("click", 1)
            time.sleep(.3)
            xdotool("click", 3)
            time.sleep(.4)
        record("background", background)
        _, table = find_cell(Atspi, app, "04 Notes.txt", 1)
        bx, by, bw, bh = extents(Atspi, table)
        for view, key in (("icon", "ctrl+1"), ("compact", "ctrl+3")):
            xdotool("key", key)
            time.sleep(1.0)

            def other_background():
                xdotool("mousemove", "--sync", bx + bw - 30, by + bh - 20)
                xdotool("click", 1)
                time.sleep(.3)
                xdotool("click", 3)
                time.sleep(.4)
            record("background-" + view, other_background)
        xdotool("key", "ctrl+2")
        time.sleep(1.0)
        side = {}
        for name in ("Computer", home.name, "Desktop", "Recent", "Trash", "Bookmarked Folder",
                     "File System", "Browse Network"):
            try:
                node = row(name, 0)
            except (AssertionError, IndexError):
                continue
            key = "side-" + ("home" if name == home.name else name.lower().replace(" ", "-"))
            record(key, lambda node=node: click(Atspi, node, 3))
            side[name] = key
        report["side_pane_rows"] = side
    finally:
        thunar.terminate()
        try:
            thunar.wait(timeout=5)
        except subprocess.TimeoutExpired:
            thunar.kill()
    (OUTPUT / "thunar.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    probe = os.environ.get("EXPLORER_MENU_PROBE")
    if not probe:
        return 0
    return compare(Path(probe), folder, home, report, env)


# Explorer has neither a column editor nor expandable list folders. These two
# details-view entries appear in Thunar's order but stay disabled in Explorer.
KNOWN = {("Configure Columns...", "sensitive"), ("Expandable Folders", "sensitive")}


def cases(folder, home):
    f = str(folder)
    trash = str(Path(os.environ["XDG_DATA_HOME"]) / "Trash/files")
    view = lambda *names, mode="list": ["view", "none", mode, f, *[str(folder / n) for n in names]]
    side = lambda kind, location: ["shortcuts", kind, "list", location, location]
    return {
        "file": view("04 Notes.txt"), "image": view("05 Image.png"), "archive": view("06 Archive.zip"),
        "executable": view("07 Script.sh"), "link": view("08 Link.txt"),
        "multiple": view("04 Notes.txt", "05 Image.png"), "mixed": view("01 Folder", "04 Notes.txt"),
        "folder": view("01 Folder"), "background": view(), "background-icon": view(mode="icon"),
        "background-compact": view(mode="compact"),
        "side-computer": side("special", "computer:///"), "side-home": side("folder", str(home)),
        "side-desktop": side("folder", str(home / "Desktop")), "side-recent": side("folder", "recent:///"),
        "side-trash": side("special", trash), "side-bookmarked-folder": side("bookmark", str(folder / "01 Folder")),
        "side-file-system": side("folder", "/"), "side-browse-network": side("special", "network:///"),
    }


def flatten(items, prefix=""):
    rows = []
    for index, item in enumerate(items):
        if item.get("separator"):
            rows.append((prefix, index, "separator", None))
            continue
        key = prefix + "/" + item["label"]
        rows.append((prefix, index, "label", item["label"]))
        rows.append((key, index, "sensitive", item["sensitive"]))
        # AT-SPI reports XFCE's draw-as-radio check items (Arrange Items) as
        # check menu items, so compare toggles by state, not indicator shape.
        rows.append((key, index, "kind", "toggle" if item.get("kind") in ("check", "radio") else "item"))
        rows.append((key, index, "checked", item.get("checked")))
        rows.append((key, index, "submenu", "submenu" in item))
        if "submenu" in item:
            rows.extend(flatten(item["submenu"], key))
    return rows


def compare(probe, folder, home, report, env):
    results = {}
    failures = []
    for name, arguments in cases(folder, home).items():
        if name not in report["menus"]:
            continue
        kind, side, mode, current, *selection = arguments
        output = subprocess.run([str(probe), kind, side, mode, "0", "1", current, *selection],
                                env=env, capture_output=True, text=True, timeout=60)
        assert output.returncode == 0, (name, output.returncode, output.stderr)
        explorer = json.loads(output.stdout)
        thunar = report["menus"][name]
        expected, actual = flatten(thunar), flatten(explorer)
        differences = []
        for row in range(max(len(expected), len(actual))):
            left = expected[row] if row < len(expected) else None
            right = actual[row] if row < len(actual) else None
            if left == right:
                continue
            if left and right and left[:3] == right[:3] and (left[0].rsplit("/", 1)[-1], left[2]) in KNOWN:
                differences.append({"known": True, "thunar": left, "explorer": right})
                continue
            differences.append({"thunar": left, "explorer": right})
        results[name] = {"explorer": explorer, "differences": differences}
        if any(not d.get("known") for d in differences):
            failures.append(name)
    (OUTPUT / "comparison.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    for name, value in results.items():
        status = "FAIL" if name in failures else "PASS"
        known = sum(1 for d in value["differences"] if d.get("known"))
        print(f"{status} {name}" + (f" ({known} known differences)" if known else ""), flush=True)
        if name in failures:
            for difference in value["differences"][:6]:
                print("   ", difference, flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
