"""Real keyboard and menu-hover regression, on the test's private Xvfb only."""
import json
import os
from pathlib import Path
import subprocess
import time
from ui_test import require_private_display, native_chrome_geometry

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / 'build/interactions'

def main():
    require_private_display()
    assert os.environ.get('EXPLORER_PRIVATE_DESKTOP') == '1'
    OUTPUT.mkdir(exist_ok=True)
    fixture = Path(os.environ['HOME']) / 'interaction-fixture'
    fixture.mkdir()
    child = fixture / 'Folder'
    child.mkdir()
    for name in ('trash.txt', 'permanent.txt', 'keypad.txt', 'editor.txt'):
        (fixture / name).write_text(name)
    def xdo(*args):
        return subprocess.check_output(['xdotool', *map(str, args)], text=True, timeout=5).strip()
    def windows():
        return subprocess.run(['xdotool','search','--onlyvisible','--class','Explorer'],capture_output=True,text=True).stdout.splitlines()
    with (OUTPUT / 'explorer.log').open('w') as log:
        process = subprocess.Popen([str(REPO/'build/explorer-desktop')],cwd=fixture,stdout=log,stderr=subprocess.STDOUT)
        owned = []
        def wait(check, reason):
            end = time.monotonic()+10
            while time.monotonic()<end:
                if check(): return
                assert process.poll() is None, 'Explorer exited: '+reason
                time.sleep(.02)
            raise AssertionError(reason)
        try:
            found=[]
            def locate():
                result=subprocess.run(['xdotool','search','--onlyvisible','--pid',str(process.pid)],capture_output=True,text=True)
                found[:]=result.stdout.splitlines()
                return bool(found)
            wait(locate,'owned window missing')
            window=found[0]; owned.append(window)
            xdo('windowsize','--sync',window,960,640);xdo('windowfocus','--sync',window)
            def key(*keys):
                xdo('key','--clearmodifiers','--window',window,*keys);time.sleep(.08)
            def type_text(text):
                xdo('type','--clearmodifiers','--window',window,'--',text);time.sleep(.08)
            def location(path):
                key('Escape','ctrl+l');type_text(str(path));key('Return');time.sleep(.15)
            def select(pattern):
                key('ctrl+s');type_text(pattern);key('Return');time.sleep(.1)
            location(fixture)
            geometry=native_chrome_geometry()
            def hover(menu):
                left,width=geometry['menus'][menu]
                xdo('mousemove','--window',window,left+width//2,geometry['menu_height']//2)
                time.sleep(.15)
            # Moving from an open File menu to Go must replace its popup.
            hover('File');xdo('click',1);time.sleep(.12);hover('Go')
            key('Home',*(['Down']*5),'Return');type_text(str(child));key('Return')
            key('ctrl+shift+n');type_text('created-after-hover');key('Return')
            wait(lambda:(child/'created-after-hover').is_dir(),'menu hover did not switch to Go/Location')
            retained=child/'created-after-hover'/'retained.txt'
            retained.write_text('retain contents across undo and redo')
            key('ctrl+z')
            wait(lambda:not retained.parent.exists(),'Ctrl+Z did not undo folder creation')
            key('ctrl+shift+z')
            wait(lambda:retained.exists(),'Ctrl+Shift+Z did not restore the same folder')
            assert retained.read_text()=='retain contents across undo and redo'
            location(fixture)
            select('Folder');key('ctrl+shift+p')
            key('ctrl+shift+n');type_text('created-in-new-tab');key('Return')
            wait(lambda:(child/'created-in-new-tab').is_dir(),'Ctrl+Shift+P did not open the selected folder in a tab')
            key('ctrl+w')
            select('editor.txt');key('F1','Delete','Escape','alt+Return','Delete','Escape')
            assert (fixture/'editor.txt').exists(),'Help or Properties leaked Delete to the file view'
            key('ctrl+Insert');location(child);key('shift+Insert')
            wait(lambda:(child/'editor.txt').exists(),'clipboard Insert aliases did not copy the file')
            key('ctrl+z');wait(lambda:not (child/'editor.txt').exists(),'Undo did not reverse clipboard copy')
            key('ctrl+shift+z');wait(lambda:(child/'editor.txt').exists(),'Redo did not repeat clipboard copy')
            location(fixture)
            select('editor.txt');key('F2','ctrl+a','Delete','Escape')
            assert (fixture/'editor.txt').read_text()=='editor.txt', 'editing Delete removed a file'
            select('permanent.txt');key('shift+Delete','Escape')
            assert (fixture/'permanent.txt').exists(),'confirmation cancel deleted the file'
            key('shift+Delete','Return')
            wait(lambda:not (fixture/'permanent.txt').exists(),'permanent confirmation did not delete')
            select('trash.txt');key('Delete')
            wait(lambda:not (fixture/'trash.txt').exists(),'Delete did not move the selection to Trash')
            trash=Path(os.environ['XDG_DATA_HOME'])/'Trash/files'
            assert any(p.is_file() and p.read_text()=='trash.txt' for p in trash.iterdir()),'Delete bypassed Trash'
            select('keypad.txt')
            state=subprocess.check_output(['xset','q'],text=True)
            import re
            mask=int(re.search(r'LED mask:\s*([0-9a-fA-F]+)',state).group(1),16)
            if mask & 2: key('Num_Lock')
            key('KP_Delete')
            wait(lambda:not (fixture/'keypad.txt').exists(),'keypad Delete did not move the file to Trash')
            key('ctrl+m','F10','Right','Home',*(['Down']*3),'Return')
            key('Escape')
            # The new-window shortcut starts the same native binary, without
            # closing the existing window; close only this private test window.
            before=set(windows());key('ctrl+n')
            new=[]
            def new_window():
                new[:]=list(set(windows())-before)
                return bool(new)
            wait(new_window,'Ctrl+N did not open an independent Explorer window')
            for extra in new:
                pid=int(xdo('getwindowpid',extra))
                assert Path(f'/proc/{pid}/exe').resolve()==(REPO/'build/explorer-desktop').resolve()
                owned.append(extra)
                xdo('windowfocus','--sync',extra);xdo('key','--window',extra,'ctrl+q')
            xdo('windowfocus','--sync',window)
            # Real (XTEST) input to the focused window: Kryon's key delivery
            # does not act on a synthetic --window event after the steps above.
            subprocess.run(['xdotool','key','--clearmodifiers','ctrl+q'],capture_output=True,timeout=5)
            assert process.wait(timeout=10)==0
            (OUTPUT/'report.json').write_text(json.dumps({'status':'passed','menu_hover':True,'keyboard_menus':True,'text_focus_delete':True,'trash_delete':True,'keypad_delete':True,'permanent_confirmation_cancel':True,'create_folder_shortcut':True,'new_window':True,'close_own_window':True},indent=2))
            print('Explorer private interaction local tests passed')
        finally:
            for window in owned:
                subprocess.run(['xdotool','key','--window',window,'ctrl+q'],capture_output=True)
            if process.poll() is None:
                process.terminate();process.wait(timeout=10)

if __name__=='__main__': main()
