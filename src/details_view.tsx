// Details list composition: the scroll viewport and its row scope run in
// TSX; selection, GTK painting and activation stay behind the app_host bridge.
import * as AppHost from "app_host";
import { Scroll } from "kryon/tsx/scroll";
import * as NativeScroll from "kryon/scroll";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";

export function DrawRows(session: Session, props: NativeScroll.Props, body: Rectangle,
        scroll_offset: s32, count: s32, row_height: s32, focused: boolean,
        modifiers: s32, physical: s32, icon_size: float32, icon_delta: float32,
        content_width: s32): NativeScroll.ScrollResult {
    return Scroll({session: session, props: props,
        children: (view: NativeScroll.ScrollResult): void => {
        AppHost.DrawDetailsRowsHost(session, body, view.scroll_offset, count, row_height,
            focused, modifiers, physical, icon_size, icon_delta, content_width);
    }});
}
