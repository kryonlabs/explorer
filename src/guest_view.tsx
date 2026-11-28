// Taiji guest screen composition: the toolbar, Actions sheet, path button,
// status line and guest shortcuts are declared here every frame from Kryon's
// public widgets. Model and filesystem logic stays native behind the app_host
// bridge; no widget draw operation is reachable from this module.
import * as AppHost from "app_host";
import * as Model from "model";
import { Button } from "kryon/tsx/button";
import { Text } from "kryon/tsx/text";
import { Wrap } from "kryon/text";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";
import { KeyDelete, KeyEscape, KeyLeft, KeyModifierAlt, KeyModifierControl,
    KeyModifierShift, KeyRight, KeyUp } from "kryon/input_protocol";

// Plain push button: Taiji never runs the GTK painter, so the widget path is
// the only visual, exactly as the native guest chrome behaved.
function GuestButton(session: Session, key: s32, label: string, bounds: Rectangle,
        enabled: boolean): boolean {
    return Button({session: session, props: {key: u64(key), bounds: bounds,
        label: label, disabled: !enabled, fit_content: true}});
}

function ActionLabel(index: s32, show_hidden: boolean): string {
    if (index === s32(0)) { return "New folder"; }
    if (index === s32(1)) { return "New file"; }
    if (index === s32(2)) { return "Copy"; }
    if (index === s32(3)) { return "Paste"; }
    if (index === s32(4)) { return "Delete…"; }
    return show_hidden ? "Hide hidden" : "Show hidden";
}

function ActionAllowed(index: s32, canCopy: boolean, canPaste: boolean,
        selected: s32): boolean {
    if (index === s32(0) || index === s32(1)) { return true; }
    if (index === s32(2)) { return canCopy; }
    if (index === s32(3)) { return canPaste; }
    if (index === s32(4)) { return selected > s32(0); }
    return true;
}

// The guest chrome strip: navigation buttons, the Actions sheet and the path
// button. Returns the path row bounds, exactly like the native original.
export function DrawChrome(session: Session, viewport: Rectangle,
        focused: boolean, key: s32): Rectangle {
    const host = nativeRef(AppHost.host);
    const manager = AppHost.ActiveManager(host);
    const enabled = focused && !AppHost.PaneLocked(host) && !host.actions_open;
    const x = viewport.x + float32(6);
    const y = viewport.y + float32(4);
    const width = viewport.width - float32(12);
    const cell = width / float32(6);
    if (GuestButton(session, s32(210), "Back", {x: x, y: y, width: cell, height: float32(28)},
            enabled && manager.back.count > s32(0))) { Model.NavigateBack(manager); }
    if (GuestButton(session, s32(211), "Forward",
            {x: x + cell, y: y, width: cell, height: float32(28)},
            enabled && manager.forward.count > s32(0))) { Model.NavigateForward(manager); }
    if (GuestButton(session, s32(212), "Up",
            {x: x + cell * float32(2), y: y, width: cell, height: float32(28)},
            enabled && manager.cwd !== "/")) { Model.NavigateUp(manager); }
    if (GuestButton(session, s32(213), "Refresh",
            {x: x + cell * float32(3), y: y, width: cell, height: float32(28)},
            enabled)) { Model.Refresh(manager); }
    if (GuestButton(session, s32(214), "Open",
            {x: x + cell * float32(4), y: y, width: cell, height: float32(28)},
            enabled && manager.cursor >= s32(0))) { AppHost.ActivateEntryHost(manager.cursor); }
    const actions: boolean = Button({session: session, props: {key: u64(227),
        bounds: {x: x + cell * float32(5), y: y, width: cell, height: float32(28)},
        label: "Actions", disabled: !focused || manager.prompt !== Model.PromptKind.PromptNone,
        selected: host.actions_open, fit_content: true}});
    if (actions) {
        nativeSet(nativeRef(host.actions_open), !host.actions_open);
    }
    if (host.actions_open && key === KeyEscape) {
        nativeSet(nativeRef(host.actions_open), false);
    }
    if (host.actions_open) {
        const selected = Model.SelectedCount(manager);
        const canCopy = selected > s32(0) && AppHost.SelectionAllFiles();
        const canPaste = manager.clipboard.paths.count > s32(0);
        const actionWidth = width / float32(3);
        for (let index = s32(0); index < s32(6); index += s32(1)) {
            const button: Rectangle = {x: x + float32(index % s32(3)) * actionWidth,
                y: y + float32(66) + float32(index / s32(3)) * float32(30),
                width: actionWidth, height: float32(30)};
            if (GuestButton(session, s32(240) + index, ActionLabel(index, manager.show_hidden),
                    button, focused && ActionAllowed(index, canCopy, canPaste, selected))) {
                nativeSet(nativeRef(host.actions_open), false);
                if (index === s32(0)) { AppHost.OpenPrompt(host, Model.PromptKind.PromptFolder); }
                else if (index === s32(1)) { AppHost.OpenPrompt(host, Model.PromptKind.PromptFile); }
                else if (index === s32(2)) { Model.CopySelection(manager, false); }
                else if (index === s32(3)) { Model.Paste(manager); }
                else if (index === s32(4)) { AppHost.ConfirmDelete(host); }
                else {
                    nativeSet(nativeRef(manager.show_hidden), !manager.show_hidden);
                    Model.Refresh(manager);
                }
            }
        }
    }
    const pathBounds: Rectangle = {x: x, y: y + float32(32), width: width, height: float32(30)};
    if (manager.prompt !== Model.PromptKind.PromptLocation) {
        const opened: boolean = Button({session: session, props: {key: u64(222), bounds: pathBounds,
            label: AppHost.GuestPathLabel(),
            disabled: !focused || AppHost.PaneLocked(host) || host.actions_open}});
        if (opened) {
            AppHost.OpenPrompt(host, Model.PromptKind.PromptLocation);
        }
    }
    return pathBounds;
}

export function DrawStatusText(session: Session, bounds: Rectangle, text: string): void {
    Text({session: session, props: {key: u64(506), bounds: bounds, text: text,
        size: s32(13), wrap: Wrap.TextWrapEllipsis}});
}

// The status line: escaped error text or the entry/selection counts.
export function DrawStatus(session: Session, viewport: Rectangle): void {
    const bounds: Rectangle = {x: viewport.x + float32(8),
        y: viewport.y + viewport.height - float32(26),
        width: viewport.width - float32(16), height: float32(22)};
    DrawStatusText(session, bounds, AppHost.GuestStatusText());
}

// Guest shortcuts yield to locked panes and the Actions sheet, like the
// native dispatch they replace.
export function DispatchShortcut(key: s32, modifiers: s32): boolean {
    const host = nativeRef(AppHost.host);
    const manager = AppHost.ActiveManager(host);
    if (key === s32(0) || AppHost.PaneLocked(host) || host.actions_open) { return false; }
    if (modifiers === KeyModifierAlt) {
        if (key === KeyLeft) { Model.NavigateBack(manager); }
        else if (key === KeyRight) { Model.NavigateForward(manager); }
        else if (key === KeyUp) { Model.NavigateUp(manager); }
        else { return false; }
    } else if (modifiers === (KeyModifierControl | KeyModifierShift) && key === s32(78)) {
        AppHost.OpenPrompt(host, Model.PromptKind.PromptFolder);
    } else if (modifiers === KeyModifierControl) {
        if (key === s32(76)) { AppHost.OpenPrompt(host, Model.PromptKind.PromptLocation); }
        else if (key === s32(82)) { Model.Refresh(manager); }
        else if (key === s32(65)) { Model.SelectAll(manager); }
        else if (key === s32(67)) { Model.CopySelection(manager, false); }
        else if (key === s32(86)) { Model.Paste(manager); }
        else if (key === s32(88)) { Model.SetError(manager, "Taiji does not provide a safe move operation"); }
        else if (key === s32(72)) {
            nativeSet(nativeRef(manager.show_hidden), !manager.show_hidden);
            Model.Refresh(manager);
        }
        else { return false; }
    } else if (modifiers === s32(0) || modifiers === KeyModifierShift) {
        if (key === KeyDelete) { AppHost.ConfirmDelete(host); }
        else if (key === s32(294)) { Model.Refresh(manager); }
        else if (key === s32(291)) { Model.SetError(manager, "Taiji does not provide a safe rename operation"); }
        else { return false; }
    } else { return false; }
    return true;
}
