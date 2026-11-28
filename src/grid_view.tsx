// File grid composition: icon and compact grid items, keyboard navigation
// flags, selection state and the click/drag/drop hit wiring run in TSX; GTK
// icon, emblem, thumbnail and scrollbar paints plus zoom, activation and
// clipboard business stay native behind the app_host bridge.
import * as AppHost from "app_host";
import * as Model from "model";
import * as NativeGridMulti from "kryon/grid_multi";
import { GridMulti } from "kryon/tsx/grid_multi";
import * as Input from "kryon/tree_input";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";
import { KeyDown, KeyEnd, KeyEnter, KeyHome, KeyLeft, KeyModifierControl,
    KeyModifierShift, KeyRight, KeyUp } from "kryon/input_protocol";

export function DrawFileGrid(session: Session, bounds: Rectangle,
        key: s32, modifiers: s32, focused: boolean, pane_index: s32): void {
    const host = nativeRef(AppHost.host);
    const manager = AppHost.PaneManagerHost(pane_index);
    const count = AppHost.GridItemsInstallHost(pane_index);
    if (count < s32(0)) { return; }
    let frame = AppHost.DetailsFrameHost(bounds);
    let props = AppHost.FileGridPropsHost(pane_index, session, frame);
    // GTK determines the viewport and whether bars consume allocation. Repeat
    // layout for a non-overlay bar, dispatching native input only on pass zero.
    const original = frame;
    for (let pass = s32(0); pass < s32(2); pass += s32(1)) {
        const layout = NativeGridMulti.GridMultiMeasure(props, count);
        const width = layout.compact ? layout.content_extent : s32(props.bounds.width);
        const height = layout.compact ? s32(props.bounds.height) : layout.content_extent;
        frame = AppHost.PrepareNativeScrollHost(pane_index, session, original,
            width, height,
            layout.compact ? manager.scroll : s32(0),
            layout.compact ? s32(0) : manager.scroll,
            layout.compact, !layout.compact, focused, pass === s32(0));
        props.bounds = frame;
        if (AppHost.NativeScrollAvailableHost(pane_index)) {
            AppHost.PaneScrollSetHost(pane_index,
                AppHost.NativeScrollValueHost(pane_index, layout.compact));
        }
    }
    const compact = manager.view_mode === Model.ViewMode.ViewCompact;
    if (AppHost.ApplyNativeWheelHost(session, pane_index, props.key, frame,
            compact, focused)) {
        AppHost.PaneScrollSetHost(pane_index,
            AppHost.NativeScrollValueHost(pane_index, compact));
    }
    props.scroll_offset = manager.scroll;
    props.external_scrollbar = AppHost.NativeScrollAvailableHost(pane_index);
    props.preserve_scroll_on_focus = true;
    props.immediate_wheel = true;
    props.invisible = true;
    props.focused = focused;
    props.disabled = !focused;
    props.control = (modifiers & KeyModifierControl) !== s32(0);
    props.shift = (modifiers & KeyModifierShift) !== s32(0);
    if (focused) {
        props.navigation.home = key === KeyHome;
        props.navigation.end = key === KeyEnd;
        props.navigation.left = key === KeyLeft;
        props.navigation.right = key === KeyRight;
        props.navigation.up = key === KeyUp;
        props.navigation.down = key === KeyDown;
        props.navigation.space = key === s32(32);
        props.navigation.enter = key === KeyEnter;
    }
    // GridMulti reveals focus on cursor, layout and viewport changes while
    // retaining independent wheel scrolling between navigation events.
    AppHost.GridRevealFocusOffHost(pane_index);
    // The item and selection Vecs are pane-owned: GridMulti applies selection
    // changes in place, so bind the views only around this call, then trim.
    const result = GridMulti({session: session, props: props,
        items: AppHost.GridItemsHost(pane_index),
        selected: AppHost.GridSelectedHost(pane_index)});
    AppHost.GridItemsTrimHost(pane_index);
    if (!result.valid) { return; }
    AppHost.GridResultApplyHost(pane_index, result.cursor, result.anchor,
        result.scroll_offset);
    AppHost.FinishNativeScrollHost(pane_index, session,
        compact ? manager.scroll : s32(0),
        compact ? s32(0) : manager.scroll, focused);
    if (AppHost.NativeScrollAvailableHost(pane_index)) {
        const value = AppHost.NativeScrollValueHost(pane_index, compact);
        AppHost.PaneScrollSetHost(pane_index, value);
        result.scroll_offset = value;
    }
    const physical = pane_index < s32(0) ? host.active_pane : pane_index;
    const pointer = Input.PointerSample(session);
    let hit = s32(-1);
    const grid_metrics = NativeGridMulti.GridMultiMeasure(props, count);
    AppHost.ListBoundsSetHost(physical, frame);
    AppHost.RecordDropRowHost(frame, manager.cwd, physical, u64(0), true);
    for (let i = s32(0); i < count; i += s32(1)) {
        const cell = NativeGridMulti.GridMultiCellBounds(grid_metrics, i,
            result.scroll_offset);
        if (cell.x + cell.width < frame.x || cell.y + cell.height < frame.y ||
                cell.x > frame.x + frame.width ||
                cell.y > frame.y + frame.height) { continue; }
        if (pointer.x >= cell.x && pointer.x < cell.x + cell.width &&
                pointer.y >= cell.y && pointer.y < cell.y + cell.height &&
                pointer.x >= frame.x && pointer.x < frame.x + frame.width &&
                pointer.y >= frame.y && pointer.y < frame.y + frame.height) {
            hit = i;
        }
        AppHost.RecordDropRowHost(cell, Model.EntryPath(manager, i), physical,
            AppHost.GridEntryKeyHost(pane_index, i),
            Model.EntryIsDirectory(manager, i));
    }
    AppHost.ViewPointerHost(session, physical, hit, frame, focused);
    AppHost.DrawNativeGridHost(pane_index, frame, props, result);
    AppHost.PaintNativeScrollHost(pane_index, session, focused);
    if (result.activated_index >= s32(0)) {
        AppHost.ActivateEntryHost(result.activated_index);
    } else if (result.clicked_index >= s32(0)) {
        AppHost.EntryClickHost(result.clicked_index, modifiers);
    }
}
