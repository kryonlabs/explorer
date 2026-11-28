// Places sidebar composition: the scroll viewport, its ordered Places,
// Devices and Network headings/rows and the open/context wiring run in TSX;
// GTK heading and row painting, drop rows and menu requests stay behind the
// app_host bridge as granular primitives and state actions.
import * as AppHost from "app_host";
import { Scroll } from "kryon/tsx/scroll";
import * as NativeScroll from "kryon/scroll";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";

function DrawHeading(y: float32, sidebar: Rectangle, markup: string): float32 {
    const height = AppHost.PlacesHeadingHeightHost();
    const bounds: Rectangle = {x: sidebar.x + float32(10), y: y,
        width: sidebar.width - float32(20), height: height};
    AppHost.PlacesHeadingPaintHost(bounds, markup);
    return y + height;
}

function DrawRow(session: Session, row: NativeRef<AppHost.PlacesRowView>, y: float32,
        sidebar: Rectangle, content: Rectangle, focused: boolean): float32 {
    const bounds: Rectangle = {x: sidebar.x, y: y, width: content.width,
        height: AppHost.PlacesRowHeightHost()};
    if (AppHost.PlacesControlPaintHost(row.key, bounds, row.label, row.icon, focused,
            row.selected, row.icon_data, row.file_icon)) {
        if (row.index >= s32(0)) { AppHost.PlacesBookmarkSelectHost(row.index); }
        AppHost.PlacesOpenHost(row.route, row.key);
    }
    AppHost.PlacesRowMenuHost(session, bounds, row.route, row.side, row.index, row.key,
        focused);
    return y + bounds.height;
}

function DrawPlacesRows(session: Session, sidebar: Rectangle, content: Rectangle,
        scroll_offset: s32, focused: boolean, has_desktop: boolean, desktop: string): void {
    AppHost.PlacesScrollHost(scroll_offset);
    AppHost.PlacesClipBeginHost(sidebar);
    let y = sidebar.y - float32(scroll_offset);
    y = DrawHeading(y, sidebar, "<b>Places</b>");
    y = DrawRow(session, AppHost.PlacesComputerRowHost(), y, sidebar, content, focused);
    y = DrawRow(session, AppHost.PlacesHomeRowHost(), y, sidebar, content, focused);
    if (has_desktop) {
        y = DrawRow(session, AppHost.PlacesDesktopRowHost(desktop), y, sidebar, content,
            focused);
    }
    y = DrawRow(session, AppHost.PlacesRecentRowHost(), y, sidebar, content, focused);
    y = DrawRow(session, AppHost.PlacesTrashRowHost(), y, sidebar, content, focused);
    const bookmarks = AppHost.PlacesBookmarksCountHost();
    for (let index = s32(0); index < bookmarks; index += s32(1)) {
        y = DrawRow(session, AppHost.PlacesBookmarkRowHost(index), y, sidebar, content,
            focused);
    }
    y = DrawHeading(y, sidebar, "<b>Devices</b>");
    y = DrawRow(session, AppHost.PlacesFilesystemRowHost(), y, sidebar, content, focused);
    const mounts = AppHost.PlacesMountsCountHost();
    for (let index = s32(0); index < mounts; index += s32(1)) {
        y = DrawRow(session, AppHost.PlacesMountRowHost(index), y, sidebar, content,
            focused);
    }
    y = DrawHeading(y, sidebar, "<b>Network</b>");
    y = DrawRow(session, AppHost.PlacesNetworkRowHost(), y, sidebar, content, focused);
    AppHost.PlacesClipEndHost();
}

export function DrawScroll(session: Session, props: NativeScroll.Props, sidebar: Rectangle,
        focused: boolean, has_desktop: boolean, desktop: string): NativeScroll.ScrollResult {
    return Scroll({session: session, props: props,
        children: (view: NativeScroll.ScrollResult): void => {
        DrawPlacesRows(session, sidebar, view.content, view.scroll_offset, focused,
            has_desktop, desktop);
    }});
}
