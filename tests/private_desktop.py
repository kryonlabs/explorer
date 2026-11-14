#!/usr/bin/env python3
"""Run only test-owned applications on a private desktop and session bus."""
import os
import errno
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def main():
    build = Path(__file__).resolve().parents[1] / "build"
    build.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="private-desktop-", dir=build))
    try:
        env = os.environ.copy()
        # Keep the user's Python packages (python-xlib for XDND probes)
        # importable after HOME moves to the private directory.
        import site
        env.setdefault("PYTHONUSERBASE", site.getuserbase())
        for key in ("DISPLAY", "WAYLAND_DISPLAY", "WAYLAND_SOCKET", "XAUTHORITY",
                    "DBUS_SESSION_BUS_ADDRESS", "SESSION_MANAGER", "ICEAUTHORITY"):
            env.pop(key, None)
        for key, folder in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"),
                            ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache"),
                            ("XDG_STATE_HOME", "state"), ("XDG_RUNTIME_DIR", "runtime"),
                            ("TMPDIR", "tmp")):
            path = root / folder
            path.mkdir(mode=0o700)
            env[key] = str(path)
        env.update(HARMONY_DESKTOP_RECOVERY="0", YUE_DESKTOP_RECOVERY="0", SDL_VIDEODRIVER="x11", GTK_USE_PORTAL="0",
                   EXPLORER_PRIVATE_DESKTOP="1", PYTHONDONTWRITEBYTECODE="1")
        command = sys.argv[1:]
        if command[0] == "--headless":
            command = command[1:]
        else:
            private = ["dbus-run-session", "--", "xvfb-run", "-a", "-s", "-screen 0 1600x1200x24", *command]
            namespace = ["unshare", "--user", "--map-current-user", "--keep-caps", "--mount",
                         "--propagation", "private"]
            # Some supervised shells forbid changing mount propagation. The
            # private bus, Xvfb display and scrubbed environment stay the same.
            probe = subprocess.run([*namespace, "true"], env=env, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
            command = [*namespace, *private] if probe.returncode == 0 else private
        return subprocess.run(command, env=env).returncode
    finally:
        # D-Bus-activated test services can finish their final state writes just
        # after the private bus exits. Retry only this owned private directory.
        for attempt in range(5):
            try:
                shutil.rmtree(root)
                break
            except FileNotFoundError:
                break
            except OSError as error:
                if error.errno != errno.ENOTEMPTY or attempt == 4: raise
                time.sleep(.1 * (attempt + 1))


if __name__ == "__main__":
    sys.exit(main())
