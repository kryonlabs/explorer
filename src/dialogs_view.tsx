// Shared confirmation and location dialogs: Empty Trash, Delete and the
// generic prompt (new folder/file, rename, goto). Composition mirrors the
// retired native dialog bodies; model actions stay in app_host behind the
// bridge. DesktopUI() reproduces the former compile-time profile gates.
import * as AppHost from "app_host";
import * as Model from "model";
import { Box } from "kryon/tsx/box";
import { Button } from "kryon/tsx/button";
import { Text } from "kryon/tsx/text";
import { ControlledTextField } from "kryon/tsx/text_field";
import { SystemClipboardSet } from "kryon/system_clipboard";
import { TextFieldInputFor } from "kryon/key_input";
import { ColorFromPacked } from "kryon/drawing_props";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";
import { KeyEnter, KeyEscape } from "kryon/input_protocol";

function DialogButton(session: Session, key: s32, label: string, bounds: Rectangle,
        enabled: boolean): boolean {
    if (AppHost.PaintButtonHost(key, bounds, label, enabled)) { return true; }
    return Button({session: session, props: {key: u64(key), id: key, bounds: bounds,
        label: label, disabled: !enabled, fit_content: true}});
}

// Desktop-only confirmation; Taiji never drew it.
export function DrawEmptyTrash(session: Session, viewport: Rectangle, key: s32,
        focused: boolean): void {
    const host = nativeRef(AppHost.host);
    if (!AppHost.DesktopUI()) { return; }
    const manager = AppHost.ActiveManager(host);
    if (manager.prompt !== Model.PromptKind.PromptEmptyTrash) { return; }
    const bounds: Rectangle = {x: viewport.x + viewport.width * float32(0.5) - float32(250),
        y: viewport.y + viewport.height * float32(0.5) - float32(55),
        width: float32(500), height: float32(110)};
    Box({session: session, props: {key: u64(50), bounds: bounds,
        fill: ColorFromPacked(host.palette.base)}});
    Text({session: session, props: {key: u64(51),
        bounds: {x: bounds.x + float32(16), y: bounds.y + float32(12),
            width: float32(468), height: float32(40)},
        text: AppHost.PromptTitle(host), size: s32(16)}});
    const cancel = DialogButton(session, s32(53), "Cancel",
        {x: bounds.x + float32(250), y: bounds.y + float32(62),
            width: float32(100), height: float32(32)}, focused)
        || (focused && key === KeyEscape);
    if (cancel) {
        nativeSet(nativeRef(manager.prompt), Model.PromptKind.PromptNone);
    } else {
        const empty = DialogButton(session, s32(54), "Empty Trash",
            {x: bounds.x + float32(364), y: bounds.y + float32(62),
                width: float32(120), height: float32(32)}, focused)
            || (focused && key === KeyEnter);
        if (empty) { AppHost.FinishEmptyTrash(host); }
    }
}

export function DrawDelete(session: Session, viewport: Rectangle, key: s32,
        focused: boolean): void {
    const host = nativeRef(AppHost.host);
    const manager = AppHost.ActiveManager(host);
    if (manager.prompt !== Model.PromptKind.PromptDelete) { return; }
    let width = float32(500);
    // Taiji clamps narrow windows; the desktop build kept the fixed width.
    if (!AppHost.DesktopUI() && viewport.width < width + float32(12)) {
        width = viewport.width - float32(12);
    }
    const bounds: Rectangle = {x: viewport.x + (viewport.width - width) * float32(0.5),
        y: viewport.y + viewport.height * float32(0.5) - float32(55),
        width: width, height: float32(110)};
    Box({session: session, props: {key: u64(50), bounds: bounds,
        fill: ColorFromPacked(host.palette.base)}});
    Text({session: session, props: {key: u64(51),
        bounds: {x: bounds.x + float32(16), y: bounds.y + float32(12),
            width: width - float32(32), height: float32(40)},
        text: AppHost.PromptTitle(host), size: s32(16)}});
    const cancel = DialogButton(session, s32(53), "Cancel",
        {x: bounds.x + width - float32(250), y: bounds.y + float32(62),
            width: float32(100), height: float32(32)}, focused);
    if (cancel) {
        nativeSet(nativeRef(manager.prompt), Model.PromptKind.PromptNone);
    } else {
        const confirmed = DialogButton(session, s32(54), "Delete",
            {x: bounds.x + width - float32(136), y: bounds.y + float32(62),
                width: float32(120), height: float32(32)}, focused)
            || (focused && key === KeyEnter);
        if (confirmed) { AppHost.FinishDelete(host); }
    }
}

// Generic location prompt: new folder/file, rename, goto and similar kinds.
export function DrawPrompt(session: Session, viewport: Rectangle, key: s32,
        modifiers: s32, typed_text: string, focused: boolean): void {
    const host = nativeRef(AppHost.host);
    const manager = AppHost.ActiveManager(host);
    if (manager.prompt === Model.PromptKind.PromptNone
            || manager.prompt === Model.PromptKind.PromptLocation
            || manager.prompt === Model.PromptKind.PromptDelete
            || manager.prompt === Model.PromptKind.PromptEmptyTrash) { return; }
    let width = float32(440);
    if (!AppHost.DesktopUI() && viewport.width < width + float32(12)) {
        width = viewport.width - float32(12);
    }
    const bounds: Rectangle = {x: viewport.x + (viewport.width - width) * float32(0.5),
        y: viewport.y + viewport.height * float32(0.5) - float32(46),
        width: width, height: float32(92)};
    Box({session: session, props: {key: u64(50), bounds: bounds,
        fill: ColorFromPacked(host.palette.base)}});
    Text({session: session, props: {key: u64(51),
        bounds: {x: bounds.x + float32(16), y: bounds.y + float32(12),
            width: width - float32(32), height: float32(22)},
        text: AppHost.PromptTitle(host), size: s32(16)}});
    const input = TextFieldInputFor(key, modifiers, typed_text);
    let fieldInput = input;
    fieldInput.focus = host.field.focused && focused;
    const edited = ControlledTextField({session: session, props: {
        key: u64(52),
        bounds: {x: bounds.x + float32(16), y: bounds.y + float32(40),
            width: width - float32(32), height: float32(32)},
        value: AppHost.FieldValueText(),
        cursor: host.field.cursor, anchor: host.field.anchor,
        scroll_x: host.field.scroll_x, focused: host.field.focused && focused,
        max_bytes: s32(4096), input: fieldInput}});
    if (edited.clipboard_write) { SystemClipboardSet(edited.clipboard_text); }
    if (focused && AppHost.FieldApplyEditHost(edited.edit)) {
        nativeSet(nativeRef(host.field.cursor), edited.cursor);
        nativeSet(nativeRef(host.field.anchor), edited.anchor);
        nativeSet(nativeRef(host.field.scroll_x), edited.scroll_x);
        if (host.field.scroll_x < s32(0)) {
            nativeSet(nativeRef(host.field.scroll_x), s32(0));
        }
        nativeSet(nativeRef(host.field.focused), edited.focused);
    }
    if (edited.committed) { AppHost.FinishPrompt(host); }
    else if (edited.escaped) {
        nativeSet(nativeRef(manager.prompt), Model.PromptKind.PromptNone);
        nativeSet(nativeRef(host.field.length), s32(0));
        nativeSet(nativeRef(host.field.focused), false);
    }
}
