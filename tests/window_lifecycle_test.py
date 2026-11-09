"""Native lifecycle and keyboard tests; private desktop only."""
import ctypes as C
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time
REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'build/window-lifecycle'
MAGIC = 0x5348454c46434c31
def wait(check, message):
    until = time.monotonic() + 10
    while time.monotonic() < until:
        if check(): return
        time.sleep(.02)
    raise AssertionError(message)
def birth(pid):
    return int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
def endpoint(pid, env=None):
    env = env or os.environ
    scope = 1469598103934665603
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR'):
        for byte in os.fsencode(env.get(key, '')) + b'\xff':
            scope = ((scope ^ byte) * 1099511628211) & ((1 << 64) - 1)
    address = bytearray(48)
    address[1:15] = b'shelf-close-v1'
    struct.pack_into('=QQQ', address, 16, scope, pid, birth(pid))
    return bytes(address)
def ready(child, env=None):
    assert child.poll() is None, f'Process exited: {child.returncode}'
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as peer:
            peer.connect(endpoint(child.pid, env))
        return True
    except (ConnectionRefusedError, FileNotFoundError): return False
def rejected_forgery(child):
    # Correct wire data from a foreign executable must never close Shelf.
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as peer:
        for data in (b'', b'x' * 40, struct.pack('=QQQ', MAGIC, birth(os.getpid()), birth(child.pid)),
                     struct.pack('=QQQ', MAGIC, birth(os.getpid()), birth(child.pid) - 1)):
            peer.sendto(data, endpoint(child.pid))
    time.sleep(.15)
    assert child.poll() is None, 'Foreign executable closed Shelf'
def main():
    assert os.environ.get('SHELF_PRIVATE_DESKTOP') == '1'
    assert os.environ.get('YUE_DESKTOP_RECOVERY') == '0'
    OUT.mkdir(exist_ok=True)
    children = []
    log = (OUT / ('probe.log' if len(sys.argv) > 1 else 'app.log')).open('w')
    report = {}
    def spawn(binary, *args, env=None):
        child = subprocess.Popen([str(binary), *args], cwd=os.environ['HOME'], env=env, stdout=log, stderr=subprocess.STDOUT)
        children.append(child)
        wait(lambda: ready(child, env), 'Native registration missing')
        return child
    try:
        if len(sys.argv) > 1:
            binary = Path(sys.argv[1]).resolve()
            for repeat in range(3):
                delayed = spawn(binary, 'delay')
                rejected_forgery(delayed)
                isolated_env = dict(os.environ, XDG_RUNTIME_DIR=os.environ['XDG_RUNTIME_DIR'] + '/isolated')
                isolated = spawn(binary, env=isolated_env)
                sender = spawn(binary, 'close')
                assert delayed.wait(timeout=5) == 0
                assert sender.wait(timeout=5) == 0
                assert isolated.poll() is None, 'Different runtime scope closed'
                isolated.terminate(); isolated.wait(timeout=5)
            report.update(delayed_acknowledgments=3, foreign_sender_rejected=True, separate_scope_preserved=True)
        else:
            binary = REPO / 'build/shelf-desktop'
            def xdo(*args):
                return subprocess.run(['xdotool', *map(str, args)], check=True, capture_output=True, text=True, timeout=5).stdout.strip()
            def window(child):
                result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(child.pid)], capture_output=True, text=True)
                return result.stdout.splitlines()
            def start():
                child = spawn(binary)
                wait(lambda: bool(window(child)), 'Shelf window missing')
                return child, window(child)[0]
            first, first_window = start()
            second, second_window = start()
            rejected_forgery(first)
            xdo('windowfocus', first_window); xdo('key', 'ctrl+q')
            assert first.wait(timeout=5) == 0
            assert second.poll() is None
            report['ctrl_q_current_only'] = True
            first, first_window = start()
            # A foreign SDL window spoofs Shelf title/class and a Shelf PID.
            os.environ['SDL_VIDEO_X11_WMCLASS'] = 'Shelf'
            sdl = C.CDLL(ctypes.util.find_library('SDL2'))
            sdl.SDL_Init.argtypes = [C.c_uint]; sdl.SDL_Init.restype = C.c_int
            assert sdl.SDL_Init(0x20) == 0
            sdl.SDL_CreateWindow.argtypes = [C.c_char_p, C.c_int, C.c_int, C.c_int, C.c_int, C.c_uint]
            sdl.SDL_CreateWindow.restype = C.c_void_p
            foreign = sdl.SDL_CreateWindow(b'Shelf', 0, 0, 200, 120, 4)
            assert foreign
            sdl.SDL_PumpEvents()
            foreign_id = xdo('search', '--pid', os.getpid()).splitlines()[0]
            subprocess.run(['xprop', '-id', foreign_id, '-f', '_NET_WM_PID', '32c', '-set', '_NET_WM_PID', str(second.pid)], check=True, capture_output=True)
            xdo('windowfocus', first_window); xdo('key', 'ctrl+shift+w')
            assert first.wait(timeout=5) == 0
            assert second.wait(timeout=5) == 0
            sdl.SDL_PumpEvents()
            assert xdo('getwindowname', foreign_id) == 'Shelf'
            sdl.SDL_DestroyWindow.argtypes = [C.c_void_p]
            sdl.SDL_DestroyWindow(foreign); sdl.SDL_Quit()
            report.update(ctrl_shift_w_all=True, spoofed_foreign_window_preserved=True, forged_datagrams_rejected=True)
        with binary.open('rb') as stream:
            report['binary_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        report['status'] = 'passed'
        name = binary.name + '-report.json'
        (OUT / name).write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, sort_keys=True))
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
        log.close()
if __name__ == '__main__': main()
