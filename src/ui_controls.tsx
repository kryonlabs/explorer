// Shared widget controls for native callers: TSX buttons with the exact
// props the former native helpers set, without any host types.
import { Button } from "kryon/tsx/button";
import { Box } from "kryon/tsx/box";
import { Text } from "kryon/tsx/text";
import { Image } from "kryon/tsx/image";
import { PanedView } from "kryon/tsx/paned_view";
import { GridMulti } from "kryon/tsx/grid_multi";
import * as NativeBox from "kryon/box";
import * as NativeText from "kryon/text";
import * as NativeButton from "kryon/button";
import * as NativeImage from "kryon/image";
import * as NativePanedView from "kryon/paned_view";
import * as NativeGridMulti from "kryon/grid_multi";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";

export function WidgetButton(session: Session, key: s32, bounds: Rectangle,
        label: string, enabled: boolean): boolean {
    return Button({session: session, props: {key: u64(key), id: key, bounds: bounds,
        label: label, disabled: !enabled, fit_content: true}});
}

// Invisible GTK-overlay hit-test button: reproduces the former native
// ButtonWidget.Draw sites exactly, including their absent fit-content refit
// (the visible button's label refit would change the submitted hit bounds),
// the explicit activation id slot and the selected flag.
export function WidgetHitButton(session: Session, key: u64, id: s32,
        bounds: Rectangle, label: string, enabled: boolean,
        selected: boolean): boolean {
    return Button({session: session, props: {key: key, id: id, bounds: bounds,
        label: label, disabled: !enabled, invisible: true, selected: selected}});
}

// Plain widget surfaces called from the native hosts: each forwards one
// ordinary props record through its public Kryon TSX component.
export function WidgetBox(session: Session, props: NativeBox.Props): s32 {
    return Box({session: session, props: props});
}

export function WidgetText(session: Session, props: NativeText.Props): void {
    Text({session: session, props: props});
}

export function WidgetImage(session: Session, props: NativeImage.Props): void {
    Image({session: session, props: props});
}

export function WidgetButtonProps(session: Session, props: NativeButton.Props): boolean {
    return Button({session: session, props: props});
}

export function WidgetPanedView(session: Session,
        props: NativePanedView.Props): NativePanedView.PanedViewResult {
    return PanedView({session: session, props: props});
}

export function WidgetGridMulti(session: Session, props: NativeGridMulti.Props,
        items: NativeGridMulti.GridMultiItem[],
        selected: boolean[]): NativeGridMulti.GridMultiResult {
    return GridMulti({session: session, props: props, items: items, selected: selected});
}
