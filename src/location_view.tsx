// Location chrome composition: breadcrumb ancestors, the Actions dropdown,
// the location editor with its completion list and the status hint. Ancestor
// sync, completion queries and row activation stay native behind the
// app_host bridge; item slices are installed on the native draw path and
// passed into these read-only TSX views.
import * as AppHost from "app_host";
import * as Model from "model";
import { Breadcrumb } from "kryon/tsx/breadcrumb";
import { Dropdown } from "kryon/tsx/dropdown";
import { ListBoxMulti } from "kryon/tsx/list_box";
import { Box } from "kryon/tsx/box";
import { Text } from "kryon/tsx/text";
import { ControlledTextField } from "kryon/tsx/text_field";
import * as NativeBreadcrumb from "kryon/breadcrumb";
import * as NativeDropdown from "kryon/dropdown";
import * as NativeListBox from "kryon/list_box";
import * as NativeTextField from "kryon/text_field";
import { SystemClipboardSet } from "kryon/system_clipboard";
import { TextFieldInputFor } from "kryon/key_input";
import { ColorFromPacked } from "kryon/drawing_props";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";
import { KeyDown, KeyEnd, KeyEnter, KeyEscape, KeyHome, KeyUp } from "kryon/input_protocol";

function LocationBreadcrumb(session: Session, bounds: Rectangle, focused: boolean,
        key: s32, synced: boolean, items: NativeBreadcrumb.BreadcrumbItem[]): s32 {
    const host = nativeRef(AppHost.host);
    const manager = AppHost.ActiveManager(host);
    if (!synced) { return s32(-1); }
    const props: NativeBreadcrumb.Props = {key: u64(220), bounds: bounds,
        active_index: AppHost.BreadcrumbCountHost() - s32(1), focused_index: s32(-1),
        focused: focused, disabled: !focused || manager.prompt !== Model.PromptKind.PromptNone,
        overflow_label: "Ancestors"};
    if (host.breadcrumb_open && focused) {
        props.menu_input = {navigating: key === KeyUp || key === KeyDown || key === KeyHome || key === KeyEnd,
            up: key === KeyUp, down: key === KeyDown, home: key === KeyHome, end: key === KeyEnd,
            commit: key === KeyEnter, escape: key === KeyEscape};
    }
    const wasOpen = host.breadcrumb_open;
    const stale = wasOpen && !AppHost.PopupOwnerValid(host);
    props.close = stale;
    const result = Breadcrumb({session: session, props: props, items: items});
    nativeSet(nativeRef(host.breadcrumb_open), result.open);
    if (result.open && !wasOpen) { AppHost.CapturePopupOwner(host); }
    AppHost.BreadcrumbTrimHost();
    if (stale) { Model.SetError(manager, "Menu owner changed; action canceled"); return s32(-1); }
    return result.activated_index;
}

export function DrawLocationBreadcrumb(session: Session, bounds: Rectangle,
        focused: boolean, key: s32, synced: boolean,
        items: NativeBreadcrumb.BreadcrumbItem[]): void {
    const first = AppHost.BreadcrumbMarkHost(session);
    const row = LocationBreadcrumb(session, bounds, focused, key, synced, items);
    AppHost.BreadcrumbTrailHost(session, bounds, first, row);
}

export function DrawNarrowActions(session: Session, bounds: Rectangle, focused: boolean,
        key: s32): boolean {
    const host = nativeRef(AppHost.host);
    const manager = AppHost.ActiveManager(host);
    const labels: [string, string, string, string, string, string, string, string, string,
        string, string, string, string, string] = ["New folder", "New file", "Rename", "Copy",
        "Paste", "Cut", "Duplicate", "Link", "Trash", "Show hidden", "Restore", "Preview",
        "Split view", "Other pane"];
    let options: [NativeDropdown.Option, NativeDropdown.Option, NativeDropdown.Option,
        NativeDropdown.Option, NativeDropdown.Option, NativeDropdown.Option, NativeDropdown.Option,
        NativeDropdown.Option, NativeDropdown.Option, NativeDropdown.Option, NativeDropdown.Option,
        NativeDropdown.Option, NativeDropdown.Option, NativeDropdown.Option] =
        [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}];
    for (let index = s32(0); index < s32(14); index += s32(1)) {
        options[index] = {key: u64(s32(300) + index), label: labels[index],
            disabled: AppHost.ActionsOptionDisabledHost(index)};
    }
    const props: NativeDropdown.Props = {key: u64(227), bounds: bounds,
        placeholder: "Actions", selected_index: s32(-1),
        disabled: !focused || manager.prompt !== Model.PromptKind.PromptNone};
    if (host.actions_open && focused) {
        props.menu_input = {navigating: key === KeyUp || key === KeyDown || key === KeyHome || key === KeyEnd,
            up: key === KeyUp, down: key === KeyDown, home: key === KeyHome, end: key === KeyEnd,
            commit: key === KeyEnter, escape: key === KeyEscape};
    }
    const wasOpen = host.actions_open;
    const stale = wasOpen && !AppHost.PopupOwnerValid(host);
    props.close = stale;
    const result = Dropdown({session: session, props: props,
        options: nativeSlice(options, s32(0), s32(14))});
    nativeSet(nativeRef(host.actions_open), result.open);
    if (result.open && !wasOpen) { AppHost.CapturePopupOwner(host); }
    if (stale) { Model.SetError(manager, "Menu owner changed; action canceled"); return true; }
    if (!result.changed) { return wasOpen || result.open; }
    const choice = result.selected_index;
    if (choice === s32(0)) { AppHost.OpenPrompt(host, Model.PromptKind.PromptFolder); }
    else if (choice === s32(1)) { AppHost.OpenPrompt(host, Model.PromptKind.PromptFile); }
    else if (choice === s32(2)) { AppHost.OpenPrompt(host, Model.PromptKind.PromptRename); }
    else if (choice === s32(3)) { AppHost.ActionsCopyHost(false); }
    else if (choice === s32(4)) { AppHost.PasteFiles(host); }
    else if (choice === s32(5)) { AppHost.ActionsCopyHost(true); }
    else if (choice === s32(6)) { AppHost.ActionsDuplicateHost(); }
    else if (choice === s32(7)) { AppHost.ActionsLinkHost(); }
    else if (choice === s32(8)) { AppHost.ActionsTrashHost(); }
    else if (choice === s32(9)) {
        nativeSet(nativeRef(manager.show_hidden), !manager.show_hidden);
        Model.Refresh(manager);
    }
    else if (choice === s32(10)) { AppHost.ActionsRestoreHost(); }
    else if (choice === s32(11) && manager.cursor >= s32(0)) { AppHost.ActionsPreviewHost(); }
    else if (choice === s32(12)) {
        nativeSet(nativeRef(host.actions_open), false);
        AppHost.ToggleSplit(host);
    }
    else if (choice === s32(13)) {
        nativeSet(nativeRef(host.actions_open), false);
        AppHost.RequestPane(host, s32(1) - host.active_pane);
    }
    return true;
}

// Key phase for the location editor: field editing plus the completion
// query. Returns true when the completion list should draw this frame; the
// native draw path refreshes the completion item cache between this call
// and DrawLocationEditorList.
export function DrawLocationEditorKeys(session: Session, bounds: Rectangle, viewport: Rectangle,
        key: s32, modifiers: s32, typed_text: string, focused: boolean): boolean {
    const host = nativeRef(AppHost.host);
    let consumed = false;
    if (AppHost.DesktopUI() && focused) { consumed = AppHost.LocationKeyHost(host, key, modifiers); }
    AppHost.CopyFieldValueHost();
    const input = TextFieldInputFor(consumed ? s32(0) : key, modifiers, consumed ? "" : typed_text);
    let fieldInput = input;
    fieldInput.focus = host.field.focused && focused;
    const edited = ControlledTextField({session: session, props: {
        key: u64(222), bounds: bounds, value: AppHost.FieldValueText(),
        cursor: host.field.cursor, anchor: host.field.anchor, scroll_x: host.field.scroll_x,
        focused: host.field.focused && focused, max_bytes: s32(4096), capture_tab: true,
        input: fieldInput}});
    if (edited.clipboard_write) { SystemClipboardSet(edited.clipboard_text); }
    if (focused && AppHost.FieldApplyEditHost(edited.edit)) {
        nativeSet(nativeRef(host.field.cursor), edited.cursor);
        nativeSet(nativeRef(host.field.anchor), edited.anchor);
        nativeSet(nativeRef(host.field.scroll_x), edited.scroll_x);
        nativeSet(nativeRef(host.field.focused), edited.focused);
        if (host.field.scroll_x < s32(0)) { nativeSet(nativeRef(host.field.scroll_x), s32(0)); }
    }
    if (edited.committed) { AppHost.FinishPrompt(host); return false; }
    if (edited.escaped) { AppHost.CancelLocationHost(host); return false; }
    if (!AppHost.DesktopUI()) { return false; }
    if (edited.edit.changed && focused) {
        nativeSet(nativeRef(host.completion_scroll), s32(0));
        AppHost.CompletionQueryHost();
    }
    return true;
}

// Draw phase for the completion popup; runs after the native cache refresh.
export function DrawLocationEditorList(session: Session, bounds: Rectangle,
        viewport: Rectangle, focused: boolean, items: NativeListBox.ListBoxItem[]): void {
    const host = nativeRef(AppHost.host);
    let height = float32(host.location.order.count) * float32(30);
    if (height > float32(240)) { height = float32(240); }
    if (bounds.y + bounds.height + height + float32(28) > viewport.y + viewport.height) {
        height = viewport.y + viewport.height - bounds.y - bounds.height - float32(28);
    }
    if (!host.location.valid) { height = float32(0); }
    if (height > float32(0)) {
        const popup: Rectangle = {x: bounds.x, y: bounds.y + bounds.height,
            width: bounds.width, height: height};
        Box({session: session, props: {key: u64(223), bounds: popup,
            fill: ColorFromPacked(host.palette.base)}});
        const count = AppHost.CompletionSyncHost();
        if (count > s32(0)) {
            const listProps: NativeListBox.ListBoxMultiProps = {key: u64(224), bounds: popup,
                row_height: s32(30), anchor: host.location.selected,
                scroll_offset: host.completion_scroll, focused: false, disabled: !focused};
            if (focused) { listProps.scroll_delta = AppHost.CompletionWheelHost(session, popup); }
            const completionFlags = AppHost.CompletionFlagsHost();
            const result = ListBoxMulti({session: session, props: listProps,
                items: items, selected: completionFlags});
            nativeSet(nativeRef(host.completion_scroll), result.scroll_offset);
            AppHost.CompletionTrimHost();
            if (result.clicked_index >= s32(0)) { AppHost.ApplyChosenLocationHost(result.clicked_index); }
        }
    }
}

export function DrawLocationStatus(session: Session, viewport: Rectangle): void {
    const host = nativeRef(AppHost.host);
    const manager = AppHost.ActiveManager(host);
    const shortWidth = viewport.width < float32(520);
    const bounds: Rectangle = {x: viewport.x + float32(166),
        y: viewport.y + viewport.height - (shortWidth ? float32(48) : float32(26)),
        width: viewport.width - float32(174), height: shortWidth ? float32(44) : float32(22)};
    if (manager.error !== "") {
        Text({session: session, props: {key: u64(228), bounds: bounds,
            text: AppHost.StatusCaptionHost(), size: s32(14)}});
    } else {
        const hint = AppHost.DesktopUI() ? "Tab completes · ↑↓ choose · Enter opens · Esc cancels"
            : "Enter opens · Esc cancels";
        Text({session: session, props: {key: u64(225), bounds: bounds,
            text: host.escaped_editor ? "Byte escapes: \xNN; \\ backslash" : hint, size: s32(14)}});
    }
}
