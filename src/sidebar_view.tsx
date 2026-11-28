// Places sidebar composition: the scroll viewport and its row scope run in
// TSX; GTK row painting and open actions stay behind the app_host bridge.
import * as AppHost from "app_host";
import { Scroll } from "kryon/tsx/scroll";
import * as NativeScroll from "kryon/scroll";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";

export function DrawScroll(session: Session, props: NativeScroll.Props, sidebar: Rectangle,
        focused: boolean, has_desktop: boolean, desktop: string): NativeScroll.ScrollResult {
    return Scroll({session: session, props: props,
        children: (view: NativeScroll.ScrollResult): void => {
        AppHost.DrawPlacesRowsHost(session, sidebar, view.content, view.scroll_offset,
            focused, has_desktop, desktop);
    }});
}
