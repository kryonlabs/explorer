# Thunar parity roadmap

Explorer's goal is feature parity with Thunar as a Ziran/Kryon application. The
statuses below describe the current Linux implementation; they are intentionally
specific so each missing row can become an independent implementation task.

| Thunar feature | Explorer status | Remaining work |
| --- | --- | --- |
| Icon view | Partial | Row-major icon grid, shared multi-selection, keyboard navigation, zoom and immediate native vertical scroll exist; add alignment preferences and rubber-band selection. |
| List view | Partial | Sortable Name/Size/Type/Modified details with resizable headers and shared multi-selection exist; add inline rename and configurable columns. |
| Compact view | Partial | Column-major layout, leading icons, zoom, shared selection and immediate native horizontal scroll exist; add persistent layout preferences. |
| Shortcuts side pane | Partial | Native Places/Devices/Network groups, XDG folders, GTK bookmarks and GVolumeMonitor device names/icons exist; add mount/unmount/eject controls and remote bookmark editing. |
| Tree side pane | Partial | Lazy local Home/File System tree, expansion state, cwd ancestor reveal, hidden filtering, explicit branch refresh, safe raw-name captions and horizontal scrolling/reveal exist. Add remote/device trees and automatic filesystem watching. |
| Location bar and path bar | Partial | Native location entry, local breadcrumbs, bounded raw-name completion and checked folder/file selection exist. GIO URI navigation retains native errors; add URI completion, authentication and broader path-bar preferences. |
| Tabs | Partial | Native stable-key labels, active state, close controls, scrolling overflow and pointer/keyboard reorder exist; dynamic tabs retain independent raw routes/history/selection/focus/scroll. Add detached windows and persistent sessions. |
| Split view | Partial | Local dual panes use a native draggable divider with independent tabs, navigation, selection, scrolling and settings, shared clipboard and explicit active-pane actions. Collapse retains the other pane in memory; add persistent layout and remote providers. |
| Open With and default apps | Partial | Files delegate to `kryon/open_uri`; add application chooser, MIME database and defaults. |
| MIME handling | Partial | GIO supplies localized MIME descriptions and theme-resolved file icons with inheritance; add MIME application/default editing. |
| Copy, move and links | Partial | Recursive copy/cut/paste, duplicate and symbolic links work; add progress, pause/cancel and conflict resolution. |
| Trash | Partial | XDG Trash/files plus `.trashinfo`, deletion timestamps, restore, Delete and confirmed Shift+Delete work; add empty trash, size and age columns. |
| Drag and drop | Missing | Add internal/file-list drag payloads, drop targets and drop-menu semantics. |
| Clipboard | Partial | Desktop X11/XWayland copy/cut/paste uses text/uri-list and x-special/gnome-copied-files, with local URI validation and internal fallback when transport is unavailable. Native Wayland and clipboard-manager persistence remain; foreign identical same-window cut generations cannot be distinguished. |
| Properties and permissions | Partial | Alt+Enter displays read-only path/name/type/size/date/owner metadata; add aggregate usage and permission/ownership editing. |
| File search | Partial | Case-insensitive recursive filename search; add filtering, content search, cancellation and result navigation. |
| Hidden files | Done | Toggle and filtered directory/search scans work. |
| Sorting | Partial | Visible Name/size/modified/filesystem-type controls, reversal and deterministic name/path ties preserve selected identities and focus; add per-folder memory and configurable secondary keys. |
| Zoom | Partial | Per-view icon levels, Ctrl+plus/minus/0, keypad variants and Ctrl+wheel work; add persistent preferences and independent text scaling. |
| Bookmarks and places | Partial | Persistent editable local GTK bookmarks preserve unsupported records and use atomic saves. Native devices and GIO locations are navigable; add remote bookmark editing. |
| Mounting and removable volumes | Partial | GVolumeMonitor discovers mounted devices and native roots; add mount/unmount/eject, open-on-insert and thunar-volman-equivalent behavior. |
| Remote locations | Partial | GIO-backed URI enumeration and checked navigation participate in history, tabs and panes. Add authentication, mounting, URI completion and remote writes. |
| Thumbnails and preview | Partial | Common-image grid thumbnails, large image preview with fit/zoom/pan/browse, bounded UTF-8 text preview and file metadata exist; add persistent Tumbler-equivalent cache, document/media providers and animated playback. |
| System theme | Partial | GTK CSS, Pango fonts, native measurements, themed icons and overlay scrollbars follow the active desktop settings. Private tests compare the complete default details window with installed Thunar; broader preferences and feature parity remain. |
| Bulk rename | Missing | Add pattern/number renaming, preview, undoable batches and conflict handling. |
| Custom actions | Missing | Add UCA discovery, command templates, execution contexts and output handling. |
| Send To | Missing | Add destination providers, file contracts and extensible menu. |
| Archive integration | Missing | Add create/extract/inspect flows through an explicit archive service. |
| FileManager1 D-Bus interfaces | Missing | Implement `org.freedesktop.FileManager1` and `org.xfce.FileManager`. |
| Keyboard shortcuts | Partial | Standard navigation, selection, file operations, Undo/Redo, tab/window, zoom, sidebar/menubar, Help/Properties and keypad aliases work. Menus switch on hover and keyboard navigation; add shortcut remapping and bindings for future features. |
| Preferences | Missing | Add persistent view, behavior, shortcuts, privacy and service preferences. |

## Current application boundaries

- `src/model.zi` owns navigation, tabs, history, selection, recursive search,
  file operations, symbolic links and XDG trash metadata.
- Linux paths and selection keys retain raw filename bytes. `src/file_display.zi`
  supplies valid UTF-8 captions and reversible byte escapes for rename/location
  editors; desktop file clipboard URI validation remains strict.
- `src/bookmarks.zi` owns GTK local bookmark records and transactional persistence;
  unsupported remote/malformed records remain unchanged during local edits.
- `src/tree_sidebar.zi` owns bounded lazy local directory state, identity checks
  and staged branch refresh; canonical DataViews TreeView owns retained tree UI.
- `src/location.zi` owns literal local paths, bounded completion snapshots and raw
  breadcrumb ancestors; canonical Kryon owns Breadcrumb, TextField and list UI.
  Checked directory navigation stages listing, selection and active-tab storage
  before committing; completion and filesystem errors retain the prior route.
- `src/app.zi` is the standalone Kryon `Frame` entry.
- `src/app_host.zi` owns widget composition and exports `Host`, `Prepare`,
  `Draw` and `Close` for direct Ziran embedding.
- Rill imports the native `explorer/app_host` module. `Draw` respects the supplied
  viewport origin and preserves host input when unfocused. `Close` releases
  model storage before the host is reused.
- A portable ZX build requires filesystem host capabilities. The current
  Linux implementation uses native filesystem APIs and supplies no portable profile.

## Remaining non-Ziran files

| File | Purpose | Replacement boundary |
| --- | --- | --- |
| `Makefile` | Developer entry point | Thin wrapper around `scripts/ziran.sh`; contains no application code. |
| `scripts/ziran.sh` | Resolves the locked or locally overridden toolchain | Thin package launcher; all product code remains Ziran. |
| `tests/location_*.py` | Private native location UI, installed Thunar key comparison and allocation/read-failure probes | Test tooling only; application paths/completion remain Ziran. |
| `tests/ui_test.py` | Exercises the standalone desktop app on private Xvfb | Test tooling only; product behavior stays in the Ziran model and Kryon UI. |

Documentation, lock data, the ignored local override and the PNG showcase are
not application implementation. No C application source remains.
