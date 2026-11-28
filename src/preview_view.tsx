// Text preview composition: the scroll viewport and its line scope run in
// TSX; line slicing and text drawing stay behind the app_host bridge.
import * as AppHost from "app_host";
import { Scroll } from "kryon/tsx/scroll";
import * as NativeScroll from "kryon/scroll";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";

export function DrawText(session: Session, props: NativeScroll.Props, bounds: Rectangle,
        pan_x: float32): NativeScroll.ScrollResult {
    return Scroll({session: session, props: props,
        children: (view: NativeScroll.ScrollResult): void => {
        AppHost.DrawPreviewTextRowsHost(session, view.viewport, view.scroll_offset,
            pan_x, bounds);
    }});
}
