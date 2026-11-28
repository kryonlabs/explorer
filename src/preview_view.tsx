// Text preview composition: the scroll viewport, the visible-line window and
// its Text widgets run in TSX; line slicing and the composed line width stay
// behind the app_host bridge.
import * as AppHost from "app_host";
import { Scroll } from "kryon/tsx/scroll";
import { Text } from "kryon/tsx/text";
import { Wrap } from "kryon/text";
import * as NativeScroll from "kryon/scroll";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";

function DrawLines(session: Session, viewport: Rectangle, scroll_offset: s32,
        pan_x: float32, bounds: Rectangle): void {
    const host = nativeRef(AppHost.host);
    nativeSet(nativeRef(host.preview.text_scroll), scroll_offset);
    const lines = AppHost.PreviewLineCountHost();
    const width = AppHost.PreviewLineWidthHost();
    for (let row = s32(0); row < lines; row += s32(1)) {
        const y = viewport.y + float32(row * s32(20) - scroll_offset);
        if (y + float32(20) >= bounds.y && y < bounds.y + bounds.height) {
            Text({session: session, props: {key: u64(row + s32(1000)),
                bounds: {x: viewport.x + float32(4) - pan_x, y: y, width: width,
                    height: float32(20)},
                text: AppHost.PreviewLineHost(row), size: s32(14), wrap: Wrap.TextWrapNone}});
        }
    }
}

export function DrawText(session: Session, props: NativeScroll.Props, bounds: Rectangle,
        pan_x: float32): NativeScroll.ScrollResult {
    return Scroll({session: session, props: props,
        children: (view: NativeScroll.ScrollResult): void => {
        DrawLines(session, view.viewport, view.scroll_offset, pan_x, bounds);
    }});
}
