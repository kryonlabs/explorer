# Thunar parity roadmap

Shelf's goal is feature parity with Thunar as a Ziran/Kryon application. The
statuses below describe the current Linux implementation; they are intentionally
specific so each missing row can become an independent implementation task.

| Thunar feature | Shelf status | Remaining work |
| --- | --- | --- |
| Icon view | Partial | Row-major icon grid, shared multi-selection, keyboard navigation and vertical scroll exist; add zoom, alignment preferences and rubber-band selection. |
| List view | Partial | Sortable Name/Size/Type/Modified details with resizable headers and shared multi-selection exist; add inline rename and configurable columns. |
| Compact view | Partial | Column-major layout, small leading icons, shared selection and horizontal scroll exist; add zoom and persistent layout preferences. |
| Shortcuts side pane | Partial | Fixed Home, File System and Trash plus persistent local GTK bookmarks with add, label rename, removal, reordering and external refresh exist; add devices and remote shortcuts. |
| Tree side pane | Missing | Add lazy directory tree, expansion state and current-location sync. |
| Location bar and path bar | Partial | Read-only path plus Ctrl+L location prompt; add breadcrumb navigation and completion. |
| Tabs | Partial | Model and visible new/previous/next/close/numbered controls exist; add labels, drag reorder and overflow. |
| Split view | Missing | Add synchronized dual-pane state and per-pane tabs/selection. |
| Open With and default apps | Partial | Files delegate to `kryon/open_uri`; add application chooser, MIME database and defaults. |
| MIME handling | Missing | Add shared MIME detection, type labels, icons and inheritance-aware choices. |
| Copy, move and links | Partial | Recursive copy/cut/paste, duplicate and symbolic links work; add progress, pause/cancel and conflict resolution. |
| Trash | Partial | XDG Trash/files plus `.trashinfo`, deletion timestamps and restore work; add permanent-delete UI, empty trash, size and age columns. |
| Drag and drop | Missing | Add internal/file-list drag payloads, drop targets and drop-menu semantics. |
| Clipboard | Partial | Desktop X11/XWayland copy/cut/paste uses text/uri-list and x-special/gnome-copied-files, with local URI validation and internal fallback when transport is unavailable. Native Wayland and clipboard-manager persistence remain; foreign identical same-window cut generations cannot be distinguished. |
| Properties and permissions | Missing | Add single/multiple summaries, usage, metadata and permission/ownership editing with errors. |
| File search | Partial | Case-insensitive recursive filename search; add filtering, content search, cancellation and result navigation. |
| Hidden files | Done | Toggle and filtered directory/search scans work. |
| Sorting | Partial | Visible Name/size/modified/filesystem-type controls, reversal and deterministic name/path ties preserve selected identities and focus; add per-folder memory and configurable secondary keys. |
| Zoom | Missing | Add view zoom levels, icon/text scaling and Ctrl+wheel shortcuts. |
| Bookmarks and places | Partial | Persistent editable local GTK bookmarks preserve unsupported records and use atomic saves; add remote navigation and device-aware places. |
| Mounting and removable volumes | Missing | Add mount discovery, mount/unmount/eject, open-on-insert and thunar-volman-equivalent behavior. |
| Remote locations | Missing | Add a GVFS-like location abstraction, credentials, mounts, connectivity and remote operation errors. |
| Thumbnails and preview | Partial | Common-image grid thumbnails, large image preview with fit/zoom/pan/browse, bounded UTF-8 text preview and file metadata exist; add persistent Tumbler-equivalent cache, document/media providers and animated playback. |
| System theme | Partial | Views, icons, prompts and previews follow the configured GTK color palette and refresh while running; add desktop font and icon-theme preferences. |
| Bulk rename | Missing | Add pattern/number renaming, preview, undoable batches and conflict handling. |
| Custom actions | Missing | Add UCA discovery, command templates, execution contexts and output handling. |
| Send To | Missing | Add destination providers, file contracts and extensible menu. |
| Archive integration | Missing | Add create/extract/inspect flows through an explicit archive service. |
| FileManager1 D-Bus interfaces | Missing | Implement `org.freedesktop.FileManager1` and `org.xfce.FileManager`. |
| Keyboard shortcuts | Partial | Layout-aware arrows, Home/End, Space/Enter, modifier ranges, Ctrl+1/2/3, navigation, location, search, select-all and Ctrl+Tab exist; complete Thunar bindings, shortcuts help and remapping. |
| Preferences | Missing | Add persistent view, behavior, shortcuts, privacy and service preferences. |

## Current application boundaries

- `src/model.zi` owns navigation, tabs, history, selection, recursive search,
  file operations, symbolic links and XDG trash metadata.
- Linux paths and selection keys retain raw filename bytes. `src/file_display.zi`
  supplies valid UTF-8 captions and reversible byte escapes for rename/location
  editors; desktop file clipboard URI validation remains strict.
- `src/bookmarks.zi` owns GTK local bookmark records and transactional persistence;
  unsupported remote/malformed records remain unchanged during local edits.
- `src/app.zi` is the standalone Kryon `Frame` entry.
- `src/app_host.zi` owns widget composition and exports `Host`, `Prepare`,
  `Draw` and `Close` for direct Ziran embedding.
- Rill imports the native `shelf/app_host` module. `Draw` respects the supplied
  viewport origin and preserves host input when unfocused. `Close` releases
  model storage before the host is reused.
- A portable ZX build requires filesystem host capabilities. The current
  Linux implementation uses native filesystem APIs and supplies no portable profile.

## Remaining non-Ziran files

| File | Purpose | Replacement boundary |
| --- | --- | --- |
| `Makefile` | Developer entry point | Thin wrapper around `scripts/ziran.sh`; contains no application code. |
| `scripts/ziran.sh` | Resolves the locked or locally overridden toolchain | Thin package launcher; all product code remains Ziran. |
| `tests/ui_test.py` | Exercises the standalone desktop app on private Xvfb | Test tooling only; product behavior stays in the Ziran model and Kryon UI. |

Documentation, lock data, the ignored local override and the PNG showcase are
not application implementation. No C application source remains.
