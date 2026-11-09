"""Actual Shelf cursors and theme-resolved window icon on a private display."""
import ctypes as C
import ctypes.util
import json
import hashlib
import os
from pathlib import Path
import subprocess
import time
from PIL import Image as PNG
from collections import Counter

REPO=Path(__file__).resolve().parents[1]
OUTPUT=REPO/'build/native-window'

def fn(lib,name,result,*args):
    f=getattr(lib,name);f.restype=result;f.argtypes=args;return f

def main():
    assert os.environ.get('SHELF_PRIVATE_DESKTOP')=='1' and os.environ['YUE_DESKTOP_RECOVERY']=='0'
    OUTPUT.mkdir(exist_ok=True)
    def binary_hash():
        with (REPO/'build/shelf-desktop').open('rb') as stream:
            return hashlib.file_digest(stream,'sha256').hexdigest()
    report={'status':'running','binary_sha256':binary_hash()}
    (OUTPUT/'report.json').write_text(json.dumps(report,indent=2))
    home=Path(os.environ['HOME']);(home/'Folder').mkdir(exist_ok=True)
    (home/'Notes.txt').write_text('Native window fixture\n')
    for index in range(120):(home/f"File {index:03d}.txt").write_text("scroll fixture\n")
    for name,colour in (('ShelfFixtureOne',(203,37,71,255)),('ShelfFixtureTwo',(29,173,211,255))):
        theme=Path(os.environ['XDG_DATA_HOME'])/'icons'/name
        (theme/'48x48/apps').mkdir(parents=True,exist_ok=True)
        (theme/'index.theme').write_text(f'[Icon Theme]\nName={name}\nDirectories=48x48/apps\nInherits=Adwaita\n[48x48/apps]\nSize=48\nContext=Applications\nType=Fixed\n')
        PNG.new('RGBA',(48,48),colour).save(theme/'48x48/apps/system-file-manager.png')
    ptr=C.c_void_p;ulong=C.c_ulong;int_=C.c_int
    x=C.CDLL('libX11.so.6');fix=C.CDLL('libXfixes.so.3');sdl=C.CDLL(ctypes.util.find_library('SDL2'))
    gtk=C.CDLL('libgtk-3.so.0');obj=C.CDLL('libgobject-2.0.so.0');pix=C.CDLL('libgdk_pixbuf-2.0.so.0')
    class Cursor(C.Structure):
        _fields_=[('x',C.c_short),('y',C.c_short),('width',C.c_ushort),('height',C.c_ushort),
                  ('xhot',C.c_ushort),('yhot',C.c_ushort),('serial',ulong),
                  ('pixels',C.POINTER(ulong)),('atom',ulong),('name',C.c_char_p)]
    connection=fn(x,'XOpenDisplay',ptr,C.c_char_p)(os.environ['DISPLAY'].encode());assert connection
    def cursor():
        fn(x,'XSync',None,ptr,int_)(connection,0)
        image=fn(fix,'XFixesGetCursorImage',C.POINTER(Cursor),ptr)(connection);assert image
        v=image.contents
        result=(v.width,v.height,v.xhot,v.yhot,tuple(v.pixels[i]&0xffffffff for i in range(v.width*v.height)))
        fn(x,'XFree',None,ptr)(image);return result
    def xdo(*args):return subprocess.check_output(['xdotool',*map(str,args)],text=True,timeout=5).strip()
    def wait(check,message):
        end=time.monotonic()+10
        while time.monotonic()<end:
            if check():return
            time.sleep(.02)
        raise AssertionError(message)
    assert fn(sdl,'SDL_Init',int_,C.c_uint)(0x20)==0
    oracle=fn(sdl,'SDL_CreateWindow',ptr,C.c_char_p,int_,int_,int_,int_,C.c_uint)(b'Cursor oracle',0,0,160,100,4);assert oracle
    # Resolve this owned SDL window once. Gtk initialization can change the
    # process application name; its stable XID remains the focus target.
    fn(sdl,'SDL_PumpEvents',None)()
    oracle_windows=xdo('search','--pid',os.getpid()).splitlines()
    assert len(oracle_windows)==1,oracle_windows
    oracle_window=int(oracle_windows[0])
    references=[];handles=[]
    for shape in (0,1):
        handle=fn(sdl,'SDL_CreateSystemCursor',ptr,int_)(shape);assert handle;handles.append(handle)
        fn(sdl,'SDL_SetCursor',None,ptr)(handle);xdo('mousemove',30,30)
        for _ in range(20):fn(sdl,'SDL_PumpEvents',None)();time.sleep(.005)
        references.append(cursor())
    arrow,text=references;assert arrow!=text
    settings_log=(OUTPUT/'settings.log').open('w')
    settings=subprocess.Popen(['xfsettingsd','--no-daemon'],stdout=settings_log,stderr=subprocess.STDOUT)
    def set_theme(name):
        subprocess.run(['xfconf-query','-c','xsettings','-p','/Net/IconThemeName','-n','-t','string','-s',name],check=True,capture_output=True)
    def expected_icon(name):
        assert fn(gtk,'gtk_init_check',int_,ptr,ptr)(None,None)
        native_settings=fn(gtk,'gtk_settings_get_default',ptr)()
        setter=obj.g_object_set;setter.restype=None;setter.argtypes=(ptr,C.c_char_p)
        setter(native_settings,b'gtk-icon-theme-name',C.c_char_p(name.encode()),None)
        theme=fn(gtk,'gtk_icon_theme_get_default',ptr)()
        image=fn(gtk,'gtk_icon_theme_load_icon',ptr,ptr,C.c_char_p,int_,int_,ptr)(theme,b'system-file-manager',48,16,None)
        assert image,'Native themed system-file-manager icon unavailable'
        try:
            width=fn(pix,'gdk_pixbuf_get_width',int_,ptr)(image);height=fn(pix,'gdk_pixbuf_get_height',int_,ptr)(image)
            channels=fn(pix,'gdk_pixbuf_get_n_channels',int_,ptr)(image);stride=fn(pix,'gdk_pixbuf_get_rowstride',int_,ptr)(image)
            data=C.string_at(fn(pix,'gdk_pixbuf_get_pixels',ptr,ptr)(image),stride*height)
            values=[width,height]
            for y in range(height):
                for x_ in range(width):
                    at=y*stride+x_*channels;r,g,b=data[at:at+3];a=data[at+3] if channels==4 else 255
                    values.append((a<<24)|(r<<16)|(g<<8)|b)
            return tuple(values)
        finally:fn(obj,'g_object_unref',None,ptr)(image)
    child=None;log=(OUTPUT/'shelf.log').open('w')
    try:
        set_theme('Adwaita')
        child=subprocess.Popen([str(REPO/'build/shelf-desktop')],cwd=home,stdout=log,stderr=subprocess.STDOUT)
        windows=[]
        def locate():
            assert child.poll() is None,'Shelf exited during native window test'
            found=subprocess.run(['xdotool','search','--onlyvisible','--pid',str(child.pid)],capture_output=True,text=True)
            windows[:]=found.stdout.splitlines();return bool(windows)
        wait(locate,'Shelf native window missing');window=int(windows[0])
        xdo('windowmove',window,200,100);xdo('windowfocus',window)
        def hover(x_,y_,expected):
            xdo('mousemove','--window',window,x_,y_)
            wait(lambda:cursor()==expected,f'Wrong native cursor at {(x_,y_)}')
        for point in ((500,300),(500,107),(20,46),(30,160)):
            hover(*point,arrow)
        xdo('key','--window',window,'ctrl+l');hover(400,46,text)
        xdo('key','--window',window,'Escape');hover(500,300,arrow)
        xdo('key','--window',window,'F10');hover(500,300,arrow)
        xdo('key','--window',window,'Escape')
        xdo('key','--window',window,'Home','F2');hover(20,46,arrow)
        xdo('key','--window',window,'Escape');hover(500,300,arrow)
        report['native_cursors']={'body':True,'row':True,'toolbar':True,'sidebar':True,'location_editor':True,'editor_exit':True}
        atom=fn(x,'XInternAtom',ulong,ptr,C.c_char_p,int_)(connection,b'_NET_WM_ICON',0)
        def icon():
            kind=ulong();fmt=int_();count=ulong();remaining=ulong();data=ptr()
            status=fn(x,'XGetWindowProperty',int_,ptr,ulong,ulong,C.c_long,C.c_long,int_,ulong,
                C.POINTER(ulong),C.POINTER(int_),C.POINTER(ulong),C.POINTER(ulong),C.POINTER(ptr))(
                connection,window,atom,0,512*512+2,0,0,C.byref(kind),C.byref(fmt),C.byref(count),C.byref(remaining),C.byref(data))
            if status or fmt.value!=32:return ()
            try:return tuple(C.cast(data,C.POINTER(ulong))[i]&0xffffffff for i in range(count.value))
            finally:fn(x,'XFree',None,ptr)(data)
        for theme in ('Adwaita','ShelfFixtureOne','ShelfFixtureTwo','Adwaita'):
            set_theme(theme);expected=expected_icon(theme)
            wait(lambda:icon()==expected,f'Window icon differs from actual GTK icon theme {theme}')
            report.setdefault('native_icon_themes',[]).append(theme)
        # Exercise the real SDL input loop and native scrollbar callers. The
        # companion source/saved Host test asserts GTK's retained held state;
        # these actual-window transitions prove events reach those callers.
        from ui_test import native_chrome_geometry
        geometry=native_chrome_geometry()
        width,height=780,520
        xdo('windowsize','--sync',window,width,height)
        top=geometry['menu_height']+geometry['toolbar_height']+geometry['frame_top']
        bottom=height-geometry['status_height']
        left=170+geometry['separator_width']
        def shot(label):
            target=OUTPUT/(label+'.png')
            subprocess.run(['import','-window',str(window),str(target)],check=True,timeout=5)
            with PNG.open(target) as captured:
                assert captured.size==(width,height)
                # Navigation compares file content, independently of an overlay
                # bar's temporary hover/fade pixels. Full windows remain saved;
                # the strict Thunar visual oracle compares all their pixels.
                return captured.convert('RGB').crop((left+10,top+10,width-40,bottom-40)).tobytes()
        def settle():
            xdo('mousemove','--window',window,400,300);time.sleep(.3)
        def bar_point(horizontal,header):
            return (left+18,bottom-2) if horizontal else (width-2,top+header+18)
        for mode,shortcut,horizontal in (('icons','ctrl+1',False),('details','ctrl+2',False),('compact','ctrl+3',True)):
            xdo('key','--window',window,shortcut,'End');time.sleep(.15)
            xdo('key','--window',window,'Home');settle()
            baseline=shot(mode+'-before')
            selection_colour,selection_count=max(((colour,count) for colour,count in Counter(zip(baseline[0::3],baseline[1::3],baseline[2::3])).items() if max(colour)-min(colour)>80),key=lambda item:item[1])
            assert selection_count>1000,f'{mode}: selection fixture is not visible'
            header=geometry['header_height'] if mode=='details' else 0
            start=bar_point(horizontal,header)
            xdo('mousemove','--window',window,*start);time.sleep(.2)
            xdo('mousedown',1);time.sleep(.12)
            held=(start[0]+130,start[1]-60) if horizontal else (start[0]-60,start[1]+130)
            xdo('mousemove','--window',window,*held);time.sleep(.12)
            held_pixels=shot(mode+'-held-outside-bar')
            assert held_pixels!=baseline,f'{mode}: native held scrollbar did not move file content'
            outside=(start[0]+220,height+20) if horizontal else (width+20,start[1]+220)
            xdo('mousemove','--window',window,*outside);xdo('mouseup',1);settle()
            released=shot(mode+'-fast-release-outside-window')
            release_colours=Counter(zip(released[0::3],released[1::3],released[2::3]))
            assert release_colours[selection_colour]<selection_count//10,f'{mode}: native outside release returned to the selected first item'
            xdo('key','--window',window,'Home');settle()
            assert shot(mode+'-home-after-release')==baseline,f'{mode}: navigation failed after release'
            # Lose focus during another held press, release on the independent
            # owned SDL oracle window, then use normal content wheel input.
            xdo('mousemove','--window',window,*start);time.sleep(.1);xdo('mousedown',1);time.sleep(.1)
            xdo('mousemove','--window',window,*held);time.sleep(.12)
            cancel_held=shot(mode+'-held-before-focus-cancel')
            cancel_colours=Counter(zip(cancel_held[0::3],cancel_held[1::3],cancel_held[2::3]))
            assert cancel_colours[selection_colour]<selection_count//10,f'{mode}: focus fixture did not drag away from the first item'
            fn(sdl,'SDL_ShowWindow',None,ptr)(oracle);fn(sdl,'SDL_PumpEvents',None)()
            with PNG.open(OUTPUT/(mode+'-held-before-focus-cancel.png')) as captured:
                focused_chrome=captured.crop((0,0,width,top)).tobytes()
            xdo('windowfocus','--sync',oracle_window)
            def focus_loss_drawn():
                shot(mode+'-focus-loss')
                with PNG.open(OUTPUT/(mode+'-focus-loss.png')) as captured:
                    return captured.crop((0,0,width,top)).tobytes()!=focused_chrome
            wait(focus_loss_drawn,f'{mode}: Shelf did not redraw its inactive chrome')
            xdo('mousemove',30,30);xdo('mouseup',1)
            xdo('windowfocus',window);settle()
            canceled=shot(mode+'-after-focus-cancel')
            assert canceled==cancel_held,f'{mode}: focus cancellation changed content position'
            xdo('click',5);time.sleep(.4)
            assert shot(mode+'-wheel-after-focus-cancel')!=canceled,f'{mode}: wheel failed after focus cancellation'
            xdo('key','--window',window,'Home');settle()
            assert shot(mode+'-recovered')==baseline,f'{mode}: normal scrolling did not recover'
            report.setdefault('native_scrollbar_views',{})[mode]={'held_across_frames':True,
                'fast_outside_release':True,'focus_cancel_preserves_nonzero_position':True,'wheel_after_reenter':True,'home_recovery':True}
        report['binary_sha256_after']=binary_hash()
        assert report['binary_sha256_after']==report['binary_sha256'],'Shelf executable changed during actual-window test'
        report['window_pid']=child.pid
        report['status']='passed'
        (OUTPUT/'report.json').write_text(json.dumps(report,indent=2))
        print('Shelf native cursors, live exact GTK window icons and all-view real-window scrollbar gestures passed',flush=True)
    except BaseException as error:
        report['status']='failed';report['failure']=str(error)
        (OUTPUT/'report.json').write_text(json.dumps(report,indent=2))
        raise
    finally:
        if child is not None and child.poll() is None:child.terminate();child.wait(timeout=5)
        log.close()
        if settings.poll() is None:settings.terminate();settings.wait(timeout=5)
        settings_log.close()
        fn(sdl,'SDL_SetCursor',None,ptr)(fn(sdl,'SDL_GetDefaultCursor',ptr)())
        for handle in handles:fn(sdl,'SDL_FreeCursor',None,ptr)(handle)
        fn(sdl,'SDL_DestroyWindow',None,ptr)(oracle);fn(sdl,'SDL_Quit',None)()
        fn(x,'XCloseDisplay',None,ptr)(connection)

if __name__=='__main__':main()
