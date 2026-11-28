// Details list composition: the header columns with drag resize and sort
// wiring, the scroll viewport, the hit button, the visible-row range and the
// Taiji row widgets run in TSX; GTK row painting, tree submission and the
// multi-select state action stay behind the app_host bridge as granular
// primitives and state actions.
import * as AppHost from "app_host";
import * as Model from "model";
import { Scroll } from "kryon/tsx/scroll";
import { Button } from "kryon/tsx/button";
import { Box } from "kryon/tsx/box";
import { Text } from "kryon/tsx/text";
import { Wrap } from "kryon/text";
import { ColorFromPacked } from "kryon/drawing_props";
import { KeyModifierControl, KeyModifierShift } from "kryon/input_protocol";
import * as NativeScroll from "kryon/scroll";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";

function DrawDesktopHeader(session: Session, body: Rectangle, header: Rectangle,
        scroll_x: s32, content_width: s32, focused: boolean): void {
    AppHost.DetailsHeaderClipBeginHost(header);
    const headerLabels: [string, string, string, string] = ["Name", "Size", "Type", "Date Modified"];
    AppHost.DetailsHeaderSurfaceHost(header);
    let x = body.x - float32(scroll_x);
    for (let column = s32(0); column < s32(4); column += s32(1)) {
        let width = float32(AppHost.DetailsColumnWidthHost(column));
        if (column === s32(3)) {
            width = body.x - float32(scroll_x) + float32(content_width) - x;
        }
        width = AppHost.DetailsHeaderDragHost(session, column, x, header, focused, width);
        const bounds: Rectangle = {x: x, y: header.y, width: width, height: header.height};
        if (AppHost.DetailsHeaderPaintHost(column, bounds, headerLabels[column], focused)) {
            AppHost.DetailsSortByColumnHost(column);
        }
        x += width;
    }
    // Dividers are above both neighboring header buttons for hit testing.
    x = body.x - float32(scroll_x);
    for (let column = s32(0); column < s32(2); column += s32(1)) {
        x += float32(AppHost.DetailsColumnWidthHost(column));
        AppHost.DetailsHeaderDividerHost(session, column, x, header, focused);
    }
    AppHost.DetailsHeaderClipEndHost();
}

function DrawTaijiHeader(session: Session, body: Rectangle, header: Rectangle,
        focused: boolean, reverse: boolean): void {
    const taijiLabels: [string, string, string, string] = ["Name", "Size", "Type", "Modified"];
    const taijiAscending: [string, string, string, string] = ["Name ↑", "Size ↑", "Type ↑", "Modified ↑"];
    const taijiDescending: [string, string, string, string] = ["Name ↓", "Size ↓", "Type ↓", "Modified ↓"];
    const host = nativeRef(AppHost.host);
    Box({session: session, props: {key: u64(610), bounds: body,
        fill: ColorFromPacked(host.palette.base)}});
    let columnCount = s32(1);
    if (body.width >= float32(490)) { columnCount = s32(4); }
    else if (body.width >= float32(270)) { columnCount = s32(2); }
    let nameWidth = body.width;
    if (columnCount === s32(4)) { nameWidth = body.width - float32(250); }
    else if (columnCount === s32(2)) { nameWidth = body.width - float32(84); }
    const widths: [float32, float32, float32, float32] = [nameWidth, float32(84), float32(66), float32(100)];
    const sortColumn = AppHost.DetailsSortColumnHost();
    let x = header.x;
    for (let column = s32(0); column < columnCount; column += s32(1)) {
        let name = taijiLabels[column];
        if (sortColumn === column) {
            name = reverse ? taijiDescending[column] : taijiAscending[column];
        }
        const bounds: Rectangle = {x: x, y: header.y, width: widths[column],
            height: header.height};
        if (Button({session: session, props: {key: u64(s32(60) + column), id: s32(60) + column,
                bounds: bounds, label: name, disabled: !focused, fit_content: true}})) {
            AppHost.DetailsSortByColumnHost(column);
        }
        x += widths[column];
    }
}

function DrawTaijiRow(session: Session, index: s32, body: Rectangle,
        rowBounds: Rectangle, row_height: s32, focused: boolean, node: s32): void {
    let columnCount = s32(1);
    if (body.width >= float32(490)) { columnCount = s32(4); }
    else if (body.width >= float32(270)) { columnCount = s32(2); }
    let nameWidth = body.width;
    if (columnCount === s32(4)) { nameWidth = body.width - float32(250); }
    else if (columnCount === s32(2)) { nameWidth = body.width - float32(84); }
    const widths: [float32, float32, float32, float32] = [nameWidth, float32(84), float32(66), float32(100)];
    const host = nativeRef(AppHost.host);
    if (AppHost.TreeScopePushHost(session, node)) {
        if (AppHost.DetailsRowSelectedHost(index)) {
            Box({session: session, props: {key: u64(1), bounds: rowBounds,
                fill: ColorFromPacked(host.palette.selected)}});
        }
        const caption = AppHost.DetailsCellCaptionHost(index);
        let sizeText = "";
        let typeText = "";
        let dateText = "";
        if (columnCount > s32(1) && !AppHost.DetailsRowIsDirectoryHost(index)) {
            sizeText = AppHost.DetailsCellSizeHost(index);
        }
        if (columnCount === s32(4)) {
            typeText = AppHost.DetailsCellTypeHost(index);
            dateText = AppHost.DetailsCellDateHost(index);
        }
        const cells: [string, string, string, string] = [caption, sizeText, typeText, dateText];
        let x = rowBounds.x;
        for (let column = s32(0); column < columnCount; column += s32(1)) {
            const bounds: Rectangle = {x: x + float32(6), y: rowBounds.y,
                width: widths[column] - float32(12), height: float32(row_height)};
            Text({session: session, props: {key: u64(s32(10) + column), bounds: bounds,
                text: cells[column], size: s32(13), wrap: Wrap.TextWrapEllipsis}});
            x += widths[column];
        }
        AppHost.TreeScopeEndHost(session);
    }
}

function DrawRowsBody(session: Session, body: Rectangle, view: NativeScroll.ScrollResult,
        count: s32, row_height: s32, focused: boolean, modifiers: s32, physical: s32,
        icon_size: float32, icon_delta: float32, content_width: s32): void {
    const host = nativeRef(AppHost.host);
    const manager = AppHost.ActiveManager(host);
    AppHost.DetailsScrollHost(view.scroll_offset);
    if (Button({session: session, props: {key: u64(649), bounds: body, invisible: true,
            disabled: !focused}})) {
        Model.ClearSelection(manager);
    }
    const scroll = view.scroll_offset;
    const first = scroll / row_height;
    let last = (scroll + s32(body.height) + row_height - s32(1)) / row_height;
    if (last >= count) { last = count - s32(1); }
    let activated = s32(-1);
    AppHost.DetailsClipBeginHost();
    for (let index = first; index <= last; index += s32(1)) {
        const yy = body.y + float32(index * row_height - scroll);
        // GTK clips partially visible rows through the same viewport.
        const rowBounds: Rectangle = {x: body.x, y: yy, width: body.width,
            height: float32(row_height)};
        const clicked = AppHost.DetailsRowClickedHost(session, index, focused);
        const node = AppHost.DetailsRowSubmitHost(session, index, rowBounds, focused);
        if (clicked) {
            AppHost.DetailsSelectRowHost(index, (modifiers & KeyModifierControl) !== s32(0),
                (modifiers & KeyModifierShift) !== s32(0));
            activated = index;
        }
        if (AppHost.DesktopUI()) {
            AppHost.DetailsRowPaintHost(session, node, index, rowBounds, body, row_height,
                physical, icon_size, icon_delta, content_width, focused);
        } else {
            DrawTaijiRow(session, index, body, rowBounds, row_height, focused, node);
        }
    }
    AppHost.DetailsClipEndHost();
    if (activated >= s32(0)) { AppHost.EntryClickHost(activated, modifiers); }
}

export function DrawRows(session: Session, props: NativeScroll.Props, body: Rectangle,
        header: Rectangle, scroll_x: s32, scroll_offset: s32, count: s32,
        row_height: s32, focused: boolean, modifiers: s32, physical: s32,
        icon_size: float32, icon_delta: float32, content_width: s32): NativeScroll.ScrollResult {
    if (AppHost.DesktopUI()) {
        DrawDesktopHeader(session, body, header, scroll_x, content_width, focused);
    } else {
        DrawTaijiHeader(session, body, header, focused, AppHost.DetailsReverseHost());
    }
    return Scroll({session: session, props: props,
        children: (view: NativeScroll.ScrollResult): void => {
        DrawRowsBody(session, body, view, count, row_height, focused, modifiers, physical,
            icon_size, icon_delta, content_width);
    }});
}
