// Explorer application entry, composed in TSX. Screen sections live in
// guest_view.tsx and later app_screen.tsx over the app_host native bridge;
// the frame here only orchestrates begin/draw/end plus the Taiji lifecycle
// exports, preserving the exact window contract of the former app.zi.
import * as AppHost from "app_host";
import { Session } from "kryon/session";
import { Rectangle } from "kryon/geometry";

export function Frame(session: Session, viewport: Rectangle): s32 {
    const focused = AppHost.DesktopFrameBegin(session);
    const hostSession = nativeInit<AppHost.HostSession>({slot: session.slot,
        epoch: session.epoch});
    const hostViewport = nativeInit<AppHost.HostViewport>({x: viewport.x,
        y: viewport.y, width: viewport.width, height: viewport.height});
    const result = AppHost.Draw(nativeRef(AppHost.host), hostSession, hostViewport,
        focused);
    AppHost.DesktopFrameEnd();
    return result;
}

// Taiji embedding lifecycle (taiji_host.zi calls App.Prepare/App.Close).
export function Prepare(): boolean {
    return AppHost.Prepare(nativeRef(AppHost.host));
}

export function Close(): void {
    AppHost.Close(nativeRef(AppHost.host));
}

// Desktop profile entry. The Kryon frame loop runs in the native bridge so
// the Taiji guest bundle never pulls desktop window hosts through this
// module; Taiji embedding keeps calling Frame/Prepare/Close directly.
export function main(): s32 {
    return AppHost.DesktopMain();
}
