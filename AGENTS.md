# explorer

A file manager written in Ziran with a Kryon interface, aiming for Thunar
parity on Linux; `make taiji` also builds a TaijiOS ZX guest. README.md is the
user reference (views, previews, shortcuts, undo); docs/THUNAR_PARITY.md
tracks feature parity; docs/TAIJI.md covers the ZX build.

## Layout

| Path | Contents |
| --- | --- |
| `src/app.zi`, `src/app_host.zi` | Application entrypoint and host wiring |
| `src/*.zi` | Bookmarks, context menus, locations, file clipboard and views |
| `tests/` | Model, host, tab, tree, clipboard and interaction tests |
| `scripts/` | Build and test helpers |
| `docs/` | TAIJI.md (ZX build), THUNAR_PARITY.md (parity table) |

## Commands

```sh
make build       # build the desktop app
make check       # type-check
make run         # build and run
make test        # model, host and operation-history tests
make test-ui     # interaction tests on a private Xvfb display
make test-thunar # Thunar comparison tests
make taiji       # build build/explorer.zx for TaijiOS
make test-guest-files  # guest filesystem fixture tests
make install     # install from the current working tree
```

## Pins

- Ziran toolchain: `5db3d3c39425d5dfe4bfe4a84e6f6e2e5a810ad0`
- Kryon: `54e5b07fc9e8d97f3a1fdb2a269dcf8c70c88572`
- data_views: `741fab805271f53eab71935a45209c7c61aaa242`

Commit as Waozi <waozi@proton.me>; ordinary changes stay in CHANGELOG's
`Unreleased` section. Tests that open windows run only on private Xvfb with
inherited display/session variables scrubbed; never the live desktop.
