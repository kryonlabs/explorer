// Tab strip composition: native-installed tab items render through Kryon's
// tab bar and the returned state (scroll, drag, activation) writes back to
// the pane view. Route sync and the focus probe stay native behind the
// app_host bridge.
import * as AppHost from "app_host";
import * as Model from "model";
import { TabBar } from "kryon/tsx/tab_bar";
import * as NativeTabBar from "kryon/tab_bar";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";
import { KeyBackspace, KeyDelete, KeyEnd, KeyHome, KeyLeft, KeyRight } from "kryon/input_protocol";

export function DrawTabs(session: Session, bounds: Rectangle,
        focused: boolean, key: s32, modifiers: s32, pane: s32, sync: s32,
        tabs: NativeTabBar.Tab[]): boolean {
    const host = nativeRef(AppHost.host);
    const view = AppHost.PaneViewAtHost(pane);
    const manager = AppHost.PaneManagerHost(pane);
    // Route sync ran on the native draw path; sync is its 0/1/2 result.
    if (sync === s32(0)) { return false; }
    const reordered = sync === s32(2);
    const active = Model.TabKey(manager, manager.active_tab);
    const reveal = view.tab_active_key !== active || reordered;
    if (reveal) {
        nativeSet(nativeRef(view.tab_dragging), false);
        nativeSet(nativeRef(view.tab_drag_from), s32(-1));
    }
    const enabled = focused && !AppHost.PaneLocked(host);
    const barFocused = AppHost.TabBarFocusedHost(session, enabled);
    const props: NativeTabBar.Props = {key: u64(238), id: s32(238), bounds: bounds,
        selected_index: manager.active_tab, min_tab_width: s32(100), max_tab_width: s32(210),
        content_sized: true, scroll_offset: view.tab_scroll, focus_selected: reveal,
        dragging: view.tab_dragging, drag_from: view.tab_drag_from,
        reorder_enabled: true, disabled: !enabled};
    props.input.focused = barFocused && modifiers === s32(0);
    props.input.left = key === KeyLeft;
    props.input.right = key === KeyRight;
    props.input.home = key === KeyHome;
    props.input.end = key === KeyEnd;
    props.input.close = key === KeyDelete || key === KeyBackspace;
    const result = TabBar({session: session, props: props, tabs: tabs});
    nativeSet(nativeRef(view.tab_scroll), result.scroll_offset);
    nativeSet(nativeRef(view.tab_dragging), result.dragging);
    nativeSet(nativeRef(view.tab_drag_from), result.drag_from);
    nativeSet(nativeRef(view.tab_active_key), active);
    if (enabled) {
        if (result.reordered_from >= s32(0)) { Model.ReorderTab(manager, result.reordered_from, result.reordered_to); }
        else if (result.closed_index >= s32(0)) { Model.CloseTab(manager, result.closed_index); }
        else if (result.activated_index >= s32(0)) { Model.SwitchTab(manager, result.activated_index); }
    }
    return props.input.focused && (key === KeyLeft || key === KeyRight ||
        key === KeyHome || key === KeyEnd || key === KeyDelete || key === KeyBackspace);
}
