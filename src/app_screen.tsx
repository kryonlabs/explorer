// Screen composition: the desktop frame (menubar, toolbar with navigation,
// pathbar/location entry, search, status bar, sidebar, tab strip, panes,
// menubar dropdowns, context menu hand-off, the info dialog and the Open With
// chooser) is laid out and wired in TSX; GTK surfaces and metrics, the menu
// action dispatch, clipboard/drag state and the chooser confirm stay behind
// the app_host bridge as granular primitives and state actions.
import * as AppHost from "app_host";
import { Box } from "kryon/tsx/box";
import { Text } from "kryon/tsx/text";
import { Button } from "kryon/tsx/button";
import { PanedView } from "kryon/tsx/paned_view";
import { Popup } from "kryon/tsx/overlay";
import { ListBoxMulti } from "kryon/tsx/list_box";
import * as NativeListBox from "kryon/list_box";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";
import { ColorFromPacked } from "kryon/drawing_props";
import { KeyEscape, KeyEnter, KeyLeft, KeyRight, KeyUp, KeyDown,
    KeyHome, KeyEnd } from "kryon/input_protocol";
import * as TabsView from "tabs_view";
import * as Model from "model";
import * as LocationView from "location_view";
import * as Input from "kryon/tree_input";
import * as Tree from "kryon/tree";
import { WidgetKind } from "kryon/widget_kind";

export function DrawScreen(session: Session, viewport: Rectangle, focused: boolean,
        key: s32, modifiers: s32, typed_text: string,
        window_focused: boolean): AppHost.ScreenResult {
    const host = nativeRef(AppHost.host);
    let screenKey = key;
    let screenFocused = focused;
    if (host.info_open) { screenFocused = false; screenKey = s32(0); }
    const chrome_height = AppHost.ChromeHeightHost();
    const path_bounds = AppHost.LocationBoundsHost(viewport);
    const sidebarHidden = host.sidebar_hidden;
    const sidebar_width = sidebarHidden ? float32(0) : float32(170);
    const separator_width = sidebarHidden ? float32(0) : AppHost.PaneSeparatorWidthHost();
    const view_x = viewport.x + sidebar_width + separator_width;
    const view_width = viewport.width - sidebar_width - separator_width;
    const breadcrumb_was_open = host.breadcrumb_open;
    DrawChrome(session, viewport, path_bounds, screenFocused, screenKey);
    if (breadcrumb_was_open || host.breadcrumb_open) { screenKey = s32(0); }
    if (!sidebarHidden) {
        const sidebar: Rectangle = {x: viewport.x, y: viewport.y + chrome_height,
            width: sidebar_width, height: viewport.height - chrome_height};
        if (AppHost.TreeModeHost()) {
            AppHost.SidebarSurfaceHost(sidebar);
            if (AppHost.DrawDirectoryTreeHost(session, sidebar, screenFocused, screenKey)) {
                screenKey = s32(0);
            }
        } else {
            AppHost.DrawNativePlacesHost(session, sidebar, screenFocused);
        }
    }
    if (separator_width > float32(0)) {
        AppHost.PaneSeparatorPaintHost({x: viewport.x + sidebar_width,
            y: viewport.y + chrome_height, width: separator_width,
            height: viewport.height - chrome_height});
    }
    const split = host.split;
    const tab_height = (AppHost.TabCountHost() > s32(1) || split)
        ? float32(32) : float32(0);
    if (!split && tab_height > float32(0)) {
        const sync = AppHost.TabSyncInstallHost(s32(-1));
        const tabs = AppHost.TabItemsHost(s32(-1));
        if (TabsView.DrawTabs(session,
                {x: view_x, y: viewport.y + chrome_height, width: view_width,
                    height: float32(32)}, screenFocused, screenKey, modifiers, s32(-1),
                sync, tabs)) {
            screenKey = s32(0);
        }
        AppHost.TabItemsTrimHost(s32(-1));
    }
    const footer = AppHost.NativeStatusBoundsHost(viewport);
    let list_bounds: Rectangle = {x: view_x, y: viewport.y + chrome_height + tab_height,
        width: view_width, height: footer.y - (viewport.y + chrome_height + tab_height)};
    if (list_bounds.width < float32(1)) { list_bounds.width = float32(1); }
    if (list_bounds.height < float32(1)) { list_bounds.height = float32(1); }
    const content_enabled = AppHost.ContentEnabledHost(screenFocused);
    if (split) {
        const pane = PanedView({session: session, props: {key: u64(548), id: s32(548),
            bounds: list_bounds, vertical: true, has_split: true,
            split: AppHost.PaneSplitHost(list_bounds.width), min_first: s32(100),
            min_second: s32(100), disabled: !content_enabled}});
        nativeSet(nativeRef(host.divider), pane.split);
        nativeSet(nativeRef(host.divider_set), true);
        AppHost.DrawPaneBody(host, session, pane.first, s32(0),
            AppHost.PaneKeyHost(s32(0), screenKey), AppHost.PaneModifiersHost(s32(0), modifiers),
            content_enabled);
        AppHost.DrawPaneBody(host, session, pane.second, s32(1),
            AppHost.PaneKeyHost(s32(1), screenKey), AppHost.PaneModifiersHost(s32(1), modifiers),
            content_enabled);
    } else {
        AppHost.DrawPaneBody(host, session, list_bounds, host.active_pane,
            AppHost.PromptNoneHost() ? screenKey : s32(0), modifiers, content_enabled);
    }
    if (host.breadcrumb_open) { AppHost.BreadcrumbRetainPaintHost(); }
    const menu_was_open = host.actions_open;
    DrawMenu(session, viewport, screenFocused, screenKey);
    if (menu_was_open) { screenKey = s32(0); }
    if (AppHost.DrawContextMenuHost(session, viewport, screenFocused, screenKey)) {
        screenKey = s32(0);
    }
    DrawInfoDialog(session, viewport, window_focused);
    return nativeInit<AppHost.ScreenResult>({key: screenKey, focused: screenFocused,
        viewport: viewport, path_bounds: path_bounds});
}

// Chrome: menubar, toolbar with navigation, pathbar or location entry, search
// and the status bar compose here over the granular native facades. Menu
// widths, toolbar metrics, the breadcrumb ancestor cache, the status message
// with its free-space refresh and the GTK icon/label paints stay native; the
// composition order, hover, clicks and the retained status text node run in
// TSX exactly as the former DrawNativeChrome did.
function DrawChrome(session: Session, viewport: Rectangle,
        path_bounds: Rectangle, focused: boolean, key: s32): void {
    const host = nativeRef(AppHost.host);
    const manager = AppHost.ActiveManager(host);
    const menu_height = AppHost.MenuHeightHost();
    if (!host.menubar_hidden) {
        AppHost.ScreenSurfaceHost({x: viewport.x, y: viewport.y,
            width: viewport.width, height: menu_height}, "menubar");
        const menu_labels: [string, string, string, string, string, string] = ["File", "Edit", "View", "Go", "Bookmarks", "Help"];
        const pointer = Input.PointerSample(session);
        let x = viewport.x;
        for (let i = s32(0); i < s32(6); i += s32(1)) {
            const width = AppHost.MenuWidthHost(i);
            const bounds: Rectangle = {x: x, y: viewport.y,
                width: width, height: menu_height};
            if (focused && host.actions_open &&
                    (pointer.x !== host.menu_pointer.x ||
                        pointer.y !== host.menu_pointer.y) &&
                    pointer.x >= x && pointer.x < x + width &&
                    pointer.y >= viewport.y &&
                    pointer.y < viewport.y + menu_height &&
                    host.menu_index !== i + s32(1)) {
                nativeSet(nativeRef(host.menu_index), i + s32(1));
                nativeSet(nativeRef(host.menu_cursor), s32(0));
                AppHost.MenuPointerStoreHost(pointer.x, pointer.y);
            }
            if (AppHost.ScreenControlHost(u64(600) + u64(i), bounds, menu_labels[i],
                    "", focused, host.actions_open && host.menu_index === i + s32(1),
                    true)) {
                const open = !host.actions_open || host.menu_index !== i + s32(1);
                nativeSet(nativeRef(host.actions_open), open);
                nativeSet(nativeRef(host.menu_index), i + s32(1));
                if (open) {
                    nativeSet(nativeRef(host.menu_cursor), s32(0));
                    AppHost.MenuPointerStoreHost(pointer.x, pointer.y);
                    AppHost.CapturePopupOwner(host);
                }
            }
            x += width;
        }
    }
    const toolbar_height = AppHost.ToolbarHeightHost();
    AppHost.ScreenSurfaceHost({x: viewport.x, y: viewport.y + menu_height,
        width: viewport.width, height: toolbar_height}, "toolbar");
    for (let i = s32(0); i < s32(4); i += s32(1)) {
        let enabled = focused && AppHost.PromptNoneHost();
        if (i === s32(0)) { enabled = enabled && manager.back.count > s32(0); }
        if (i === s32(1)) { enabled = enabled && manager.forward.count > s32(0); }
        let nav_key = u64(0);
        let nav_label = "";
        let nav_icon = "";
        if (i === s32(0)) {
            nav_key = u64(1); nav_label = "Back"; nav_icon = "go-previous-symbolic";
        } else if (i === s32(1)) {
            nav_key = u64(616); nav_label = "Forward"; nav_icon = "go-next-symbolic";
        } else if (i === s32(2)) {
            nav_key = u64(2); nav_label = "Up"; nav_icon = "go-up-symbolic";
        } else {
            nav_key = u64(3); nav_label = "Home"; nav_icon = "go-home-symbolic";
        }
        if (AppHost.ScreenControlHost(nav_key,
                AppHost.ToolbarItemHost(viewport, i, false), nav_label, nav_icon,
                enabled, false, true)) {
            if (i === s32(0)) { Model.NavigateBack(manager); }
            else if (i === s32(1)) { Model.NavigateForward(manager); }
            else if (i === s32(2)) { Model.NavigateUp(manager); }
            else { Model.OpenPathTracked(manager, Model.HomePath()); }
        }
    }
    const location_prompt = AppHost.LocationPromptHost();
    if (!location_prompt && host.pathbar && !Model.IsUri(manager.cwd)) {
        const synced = AppHost.BreadcrumbCacheInstall(host, manager);
        LocationView.DrawLocationBreadcrumb(session, path_bounds, focused, key,
            synced, AppHost.BreadcrumbItemsHost());
        AppHost.BreadcrumbItemsTrimHost();
    }
    if (!location_prompt && (!host.pathbar || Model.IsUri(manager.cwd))) {
        AppHost.ScreenSurfaceHost(path_bounds, "entry");
        const caption = AppHost.LocationCaptionHost();
        if (Button({session: session, props: {key: u64(226), bounds: path_bounds,
                label: caption, invisible: true, disabled: !focused}})) {
            AppHost.OpenPrompt(host, Model.PromptKind.PromptLocation);
        }
        const icon_bounds = AppHost.LocationIconHost(path_bounds);
        if (Model.IsUri(manager.cwd)) {
            AppHost.ScreenIconHost(icon_bounds,
                manager.cwd === "computer:///" ? "computer"
                : manager.cwd === "recent:///" ? "document-open-recent"
                : "network-workgroup");
        } else {
            AppHost.ScreenFileIconHost(icon_bounds, manager.cwd);
        }
        AppHost.ScreenLabelHost(AppHost.LocationTextHost(path_bounds), caption,
            "entry");
    }
    if (AppHost.ScreenControlHost(u64(614),
            AppHost.ToolbarItemHost(viewport, s32(0), true), "Search",
            "system-search-symbolic", focused, false, true)) {
        AppHost.OpenPrompt(host, Model.PromptKind.PromptSearch);
    }
    const status = AppHost.NativeStatusBoundsHost(viewport);
    AppHost.ScreenSurfaceHost(status, "statusbar");
    const has_error = manager.error !== "";
    const message = AppHost.StatusBarMessageHost();
    AppHost.ScreenStatusLabelHost(status, message, has_error);
    const node = Tree.TreeSubmitCurrent(session,
        has_error ? u64(21) : u64(242), s32(WidgetKind.WidgetKindText), status);
    Tree.TreeSetLabel(session, node, message);
}
// Menubar dropdown: popup lifecycle, key navigation, hover, geometry and the
// per-item paint run here; label tables, shortcuts and the action dispatch
// stay native so the menu keeps one source of truth for its state.
function DrawMenu(session: Session, viewport: Rectangle, focused: boolean,
        key: s32): void {
    const host = nativeRef(AppHost.host);
    if (!host.actions_open) { return; }
    if (!AppHost.PopupOwnerValid(host) || key === KeyEscape) {
        nativeSet(nativeRef(host.actions_open), false);
        return;
    }
    const count = AppHost.MenuCountHost();
    if (focused && (key === KeyLeft || key === KeyRight)) {
        nativeSet(nativeRef(host.menu_index),
            (host.menu_index + (key === KeyLeft ? s32(4) : s32(6))) % s32(6) + s32(1));
        nativeSet(nativeRef(host.menu_cursor), s32(0));
    }
    if (focused) {
        if (key === KeyUp) {
            nativeSet(nativeRef(host.menu_cursor),
                (host.menu_cursor + count - s32(1)) % count);
        }
        if (key === KeyDown) {
            nativeSet(nativeRef(host.menu_cursor), (host.menu_cursor + s32(1)) % count);
        }
        if (key === KeyHome) { nativeSet(nativeRef(host.menu_cursor), s32(0)); }
        if (key === KeyEnd) { nativeSet(nativeRef(host.menu_cursor), count - s32(1)); }
    }
    let x = viewport.x + AppHost.MenuOffsetHost(host.menu_index - s32(1));
    let label_width = s32(0);
    let shortcut_width = s32(0);
    for (let i = s32(0); i < count; i += s32(1)) {
        const lw = AppHost.MenuTextWidthHost(AppHost.MenuItemLabelHost(i), s32(0));
        const sw = AppHost.MenuTextWidthHost(AppHost.MenuShortcutTextHost(i), s32(1));
        if (lw > label_width) { label_width = lw; }
        if (sw > shortcut_width) { shortcut_width = sw; }
    }
    const width = float32(label_width + shortcut_width +
        AppHost.MenuStylePaddingHost() + s32(40));
    if (x + width > viewport.x + viewport.width) {
        x = viewport.x + viewport.width - width;
    }
    const bounds: Rectangle = {x: x, y: viewport.y + AppHost.MenuHeightHost(),
        width: width, height: float32(count * s32(28) + s32(8))};
    const popup = Popup({session: session, props: {key: u64(650), bounds: bounds,
        keep_bounds: {x: viewport.x, y: viewport.y, width: viewport.width,
            height: AppHost.MenuHeightHost()}}});
    if (popup.closed) {
        nativeSet(nativeRef(host.actions_open), false);
        return;
    }
    if (popup.panel_node < s32(0) || !AppHost.TreeScopePushHost(session, popup.panel_node)) {
        return;
    }
    AppHost.ScreenSurfaceHost(bounds, "menu");
    AppHost.MenuPointerHoverHost(session, focused, x, width, bounds, count);
    const cursor = host.menu_cursor;
    for (let i = s32(0); i < count; i += s32(1)) {
        const clicked = AppHost.MenuItemPaintHost(session, i,
            {x: x + float32(4), y: bounds.y + float32(4) + float32(i * s32(28)),
                width: width - float32(8), height: float32(28)},
            AppHost.MenuItemLabelHost(i), focused, i === cursor,
            AppHost.MenuShortcutTextHost(i));
        if (!clicked && !(focused && key === KeyEnter && i === cursor)) { continue; }
        nativeSet(nativeRef(host.actions_open), false);
        AppHost.RunMenuActionHost(host.menu_index, i);
    }
    AppHost.TreeScopeEndHost(session);
}

// Info dialog: the centered window surface and its Close control compose here;
// the title/body text and the GTK paint primitives stay behind facades.
function DrawInfoDialog(session: Session, viewport: Rectangle,
        window_focused: boolean): void {
    const host = nativeRef(AppHost.host);
    if (!host.info_open) { return; }
    const bounds: Rectangle = {
        x: viewport.x + (viewport.width - float32(620)) * float32(0.5),
        y: viewport.y + (viewport.height - float32(420)) * float32(0.5),
        width: float32(620), height: float32(420)};
    AppHost.ScreenSurfaceHost(bounds, "window");
    AppHost.ScreenLabelHost({x: bounds.x + float32(20), y: bounds.y + float32(12),
        width: bounds.width - float32(40), height: float32(28)},
        AppHost.InfoTitleHost(), "label");
    AppHost.ScreenLabelHost({x: bounds.x + float32(20), y: bounds.y + float32(48),
        width: bounds.width - float32(40), height: bounds.height - float32(110)},
        AppHost.InfoBodyHost(), "label");
    if (AppHost.ScreenControlHost(u64(55),
            {x: bounds.x + bounds.width - float32(120),
                y: bounds.y + bounds.height - float32(46), width: float32(100),
                height: float32(32)}, "Close", "", window_focused)) {
        nativeSet(nativeRef(host.info_open), false);
    }
}

// Open With / Set Default chooser: the modal boxes, application list, remember
// toggle and confirm wiring compose here; installing items, launching the
// chosen application and closing stay native behind the facade bridge.
export function DrawChooserView(session: Session, viewport: Rectangle,
        focused: boolean, key: s32): void {
    const host = nativeRef(AppHost.host);
    if (!AppHost.ChooserOpenHost()) { return; }
    if (focused && key === KeyEscape) {
        AppHost.ChooserCloseHost();
        return;
    }
    const bounds: Rectangle = {
        x: viewport.x + (viewport.width - float32(520)) * float32(0.5),
        y: viewport.y + (viewport.height - float32(480)) * float32(0.5),
        width: float32(520), height: float32(480)};
    Box({session: session, props: {key: u64(8300), bounds: viewport}});
    Box({session: session, props: {key: u64(8301), bounds: bounds,
        fill: ColorFromPacked(host.palette.base)}});
    Text({session: session, props: {key: u64(8302),
        bounds: {x: bounds.x + float32(16), y: bounds.y + float32(12),
            width: bounds.width - float32(32), height: float32(24)},
        text: AppHost.ChooserTitleHost(), size: s32(16)}});
    const count = AppHost.ChooserItemsInstallHost();
    if (count < s32(0)) { return; }
    const items = AppHost.ChooserItemsHost();
    const flags = AppHost.ChooserFlagsHost();
    const list: Rectangle = {x: bounds.x + float32(16), y: bounds.y + float32(44),
        width: bounds.width - float32(32), height: bounds.height - float32(140)};
    const listProps: NativeListBox.ListBoxMultiProps = {key: u64(8303), bounds: list,
        row_height: s32(30), anchor: AppHost.ChooserSelectedHost(),
        scroll_offset: AppHost.ChooserScrollHost(), focused: focused};
    listProps.scroll_delta = AppHost.ChooserWheelHost(session, list);
    const result = ListBoxMulti({session: session, props: listProps,
        items: items, selected: flags});
    AppHost.ChooserScrollSetHost(result.scroll_offset);
    if (result.clicked_index >= s32(0)) {
        AppHost.ChooserSelectHost(result.clicked_index);
    }
    const remember = AppHost.ChooserRememberHost()
        ? "[x] Use as default for this kind of file"
        : "[ ] Use as default for this kind of file";
    if (Button({session: session, props: {key: u64(8304), id: s32(8304),
            bounds: {x: bounds.x + float32(16),
                y: bounds.y + bounds.height - float32(88),
                width: bounds.width - float32(32), height: float32(30)},
            label: remember,
            disabled: !(focused && !AppHost.ChooserDefaultHost())}})) {
        AppHost.ChooserToggleRememberHost();
    }
    if (Button({session: session, props: {key: u64(8305), id: s32(8305),
            bounds: {x: bounds.x + bounds.width - float32(236),
                y: bounds.y + bounds.height - float32(46), width: float32(100),
                height: float32(32)}, label: "Cancel", disabled: !focused}})) {
        AppHost.ChooserCloseHost();
        return;
    }
    const confirm = AppHost.ChooserDefaultHost() ? "Set Default" : "Open";
    const confirmed = Button({session: session, props: {key: u64(8306), id: s32(8306),
        bounds: {x: bounds.x + bounds.width - float32(126),
            y: bounds.y + bounds.height - float32(46), width: float32(110),
            height: float32(32)}, label: confirm,
        disabled: !(focused && AppHost.ChooserSelectedHost() >= s32(0))}});
    if (confirmed || (focused && key === KeyEnter &&
            AppHost.ChooserSelectedHost() >= s32(0))) {
        AppHost.ChooserConfirmHost();
    }
}
