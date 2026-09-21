#include "shelf.h"

int
main(int argc, char **argv)
{
    FileManager manager;

    InitWindow(900, 620, "Files");
    SetTargetFPS(60);
    SetDefaultFontAutoLoad(1);
    InitInterface(GetScreenWidth(), GetScreenHeight(), 1.0f);
    RefreshSystemTheme();
    SetThemeSource(THEME_SOURCE_SYSTEM);
    SetThemeMode(THEME_MODE_SYSTEM);
    SetCurrentTheme(0, GetEffectiveThemeDarkMode() ? 1 : 0);
    EnsureDefaultFont();
#ifdef KRYON_NATIVE_PLAN9
    FileManagerInit(&manager, argc > 1 ? argv[1] : getenv("home"));
#else
    FileManagerInit(&manager, argc > 1 ? argv[1] : NULL);
#endif
    FileManagerSetFocused(&manager, 1);

    while(!WindowShouldClose()) {
        BeginDrawing();
        ClearBackground(GetThemeBackground());
        BeginInterfaceFrame(GetScreenWidth(), GetScreenHeight(), 1.0f);
        FileManagerResize(&manager, GetScreenWidth(), GetScreenHeight());
        {
            Rectangle viewport = {0, 0, GetScreenWidth(), GetScreenHeight()};

            FileManagerDraw(&manager, viewport);
        }
        EndInterfaceFrame();
        EndDrawing();
    }
    CloseWindow();
    return 0;
}
