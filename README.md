# Explorer

Explorer is an independent Linux file manager written in Ziran with a Kryon
user interface. Its goal is full Thunar parity; the current implementation
covers basic navigation and file operations. It runs as a standalone desktop
application.

Use View → Icons, Detailed List or Compact List, or Ctrl+1, Ctrl+2 and Ctrl+3, to change
views. All views share selection, focus and sorting. Ctrl-click toggles a file;
Shift extends a range; Ctrl+Shift adds a range. Arrows follow the layout,
Home/End reach its ends, Ctrl moves focus without changing selection, Space
toggles selection and Enter opens the focused item. Double-click opens an item.

Images open in a large built-in preview. Use Fit, 100%, +/−, arrows and the
wheel to zoom or pan; Shift+wheel pans horizontally. Previous/Next or PgUp/PgDn
browse images. Open delegates to the desktop's default application; Esc closes
the preview. File → Preview or Ctrl+P also previews the focused file.
UTF-8 text previews read at most 64 KiB and scroll with arrows, Home/End,
PgUp/PgDn or the wheel. Other files show metadata and an Open action.

Common image files have thumbnails in the grid views. PNG, JPEG, WebP, GIF,
BMP, TIFF and SVG previews are tested with the native desktop backend; other
image formats depend on the installed Kryon codecs. Animated images show a
still frame. Missing, unreadable or undecodable files show an explicit message.

Explorer's Linux chrome uses GTK3 CSS, Pango text and the active icon theme through
Kryon's native GTK bridge. Theme inheritance, SVG/PNG/symbolic icons and file
MIME descriptions use GTK/GIO discovery. No theme assets or machine-specific
theme paths are bundled. Native theme changes invalidate cached artwork.
The menubar exposes file actions, view settings, navigation and bookmarks; the
compact toolbar provides Back, Forward, Up, Home and the editable location.
GTK measures menu items, toolbar allocations, the location entry and pane
separator; their dimensions follow the active font and theme.
Embedded drawing restores the caller's palette after each Explorer viewport.

Open menus switch on hover. F10 or Alt+F/E/V/G/B/H opens a menu; arrows, Home,
End, Enter and Escape navigate it. Menu labels show their shortcuts. Delete
(including keypad Delete with NumLock off) moves selected files to Trash;
Shift+Delete requires permanent-deletion confirmation. Editors retain Delete,
selection and clipboard keys. Mouse wheels apply GTK's page-based distance
immediately, retaining fractional offsets between notches.

F1 opens Explorer Help; Alt+Enter shows read-only file properties. F2 renames,
Ctrl+Shift+N creates a folder, Ctrl+H toggles hidden files, F5/Ctrl+R reloads,
Ctrl+S selects by pattern and Ctrl+Shift+I inverts selection. Alt+Left/Right
and Backspace use history; Alt+Up goes to the parent and Alt+Home goes home.
Ctrl+L/Alt+D edits the location. F9 toggles the sidebar; Ctrl+M toggles the
menubar. Ctrl++/=/−/0 (and keypad variants) changes or resets the active view's
icon size; Ctrl+wheel zooms the view. Ctrl+N opens a window, Ctrl+Shift+P/O opens the selected directory
in a tab/window. Ctrl+Q closes the current window; Ctrl+Shift+W closes all Explorer
windows from the same executable on the current display.

Ctrl+Z and Ctrl+Shift+Z undo and redo file operations as batches, including
creation, rename, copy, cut, links, Trash and restore. Undo keeps created or
copied objects intact in private recovery storage, including later content
changes. Replacement objects and occupied destinations are preserved with an
error. Permanent deletion clears operation history and cannot be undone.

Linux filenames retain their original bytes. Views, current paths, errors and
preview headings display invalid UTF-8 bytes and control bytes as `\xNN`;
literal backslashes display as `\\`, so names remain distinct. Valid Unicode
is preserved. Rename and Location keep ordinary input literal, including
backslashes. When the existing name or path contains invalid UTF-8 or control
bytes, the editor explicitly shows byte-escape mode: `\xFF` enters byte FF
and `\\` enters a literal backslash. Malformed hexadecimal escapes and NUL
in that mode are rejected without changing the filesystem; an escaped path
that exceeds the editor's capacity reports an error instead of being truncated.
Desktop clipboard publication still rejects paths that cannot be UTF-8 URIs.

The default location bar shows the current path. View → Pathbar switches to
clickable local breadcrumbs. Its Ancestors menu retains
hidden parents when the bar is narrow; clicking the current folder refreshes it.
Clicking the path or Ctrl+L opens an inline location editor with the current path
selected. Enter opens a folder, or selects a regular file in its parent without
executing it. Escape cancels without changing the route, selection or history.
Relative paths resolve against the folder where editing started; `~` and `~/`
use Home. Input is literal, with no shell evaluation or named-user expansion.
URI locations use GIO, including relative paths from a URI location; local
completion is available for local paths. These local file/directory semantics follow
[current upstream Thunar's location entry](https://raw.githubusercontent.com/xfce-mirror/thunar/master/thunar/thunar-location-entry.c).
The installed Thunar 4.20.2 uses file launch instead; private native comparison
there covers completion keys and cancellation, while Explorer tests verify safe
file-parent selection directly.

Tab at the end inserts the common prefix, appending `/` for one matching folder;
otherwise it first moves to the end. Up/Down cycle the displayed suggestions;
Enter navigates and clicking a suggestion fills the editor. Completion includes
hidden entries, lists folders first and uses case-sensitive raw-name prefixes.
Raw-byte or control-byte completions switch explicitly to byte-escape mode.
An ordinary backslash remains literal until that mode is shown. Completion reads
at most 65536 entries and retains at most 4096 matches; these limits do not cap
folder listings. Missing, inaccessible, changed or unrepresentable paths retain
the input and prior route. Stale suggestions require Tab to refresh.
Directory listings and active-tab text commit only after a complete checked read;
failed Back/Forward navigation retains history. Independent filesystem changes
can still race after the final identity recheck. Paths are limited to 4095 raw
bytes, editor text to 4096 bytes and breadcrumbs to 2048 ancestors.

Tabs show lossless folder-name labels with a distinct active state and stable
identities, including duplicate names. Ctrl+L reveals the full active path.
Use + or Ctrl+T to duplicate the current folder into a new tab; close buttons
or Ctrl+W close a tab; Ctrl+W closes the window when only one tab remains. Ctrl+Tab and
Ctrl+Shift+Tab cycle; Ctrl+PageUp/PageDown switch adjacent tabs and
Ctrl+Shift+PageUp/PageDown move the active tab. When the strip has keyboard
focus, Left/Right and Home/End select tabs and Delete closes one.
Drag a visible tab to reorder it, or scroll the strip to reach hidden tabs;
keyboard selection reveals the active tab. Tab storage grows until allocation
limits, with no fixed tab-count ceiling.

Each tab retains its raw folder, navigation history, selection, focused entry,
scroll, view/sort/hidden settings and cached search. Switching checks the target
folder completely before changing the active route; surviving entries restore
selection by raw path and filesystem identity. A missing, unreadable, changing
or allocation-failed target leaves the previous usable tab active, including
when closing the active tab. Search results remain cached until refresh.
Detached windows and persistent sessions are not implemented.

F3 or View → Split view opens two local panes with a draggable divider. Each
pane keeps its own tabs, history, selection, scrolling, view settings, search
and Tree state. Click a pane or use View → Other pane to make it active; the shared
location bar, sidebar and file actions follow that pane. Tab traversal,
Ctrl+Tab tab cycling and location completion keep their existing shortcuts.
Editors, previews and open menus retain their original pane until dismissed.

Disabling Split view shows the active pane across the full file area. Explorer keeps the other
pane and its tabs in memory; F3 restores it after a checked refresh. An unreadable
or allocation-failed pane stays hidden with an error, while the usable pane
remains available. This retention lasts only for the current Host lifetime.
The shared file clipboard supports copy/cut between panes, including native
desktop interchange and the internal fallback without a display. Failed refresh
of the other pane cannot undo an already completed file operation.

The Places sidebar loads local shortcuts from `$XDG_CONFIG_HOME/gtk-3.0/bookmarks`
(or `$HOME/.config/gtk-3.0/bookmarks`). If that file is absent, it reads
`$HOME/.gtk-bookmarks`; the first edit writes the GTK3 location and leaves the
legacy file intact. The Bookmarks menu actions Add current folder, Rename bookmark, Remove bookmark,
Move bookmark up and Move bookmark down edit the selected
local bookmark and preserve its folder identity. The scrolling list opens a
bookmark on each click. Existing duplicate records are preserved; adding an
already-bookmarked folder selects its first record.

Storage follows the [GTK bookmark format](https://raw.githubusercontent.com/GNOME/gtk/gtk-3-24/gtk/gtkbookmarksmanager.c)
also used by [Thunar](https://raw.githubusercontent.com/xfce-mirror/thunar/master/thunar/thunar-shortcuts-model.c).
Unsupported remote, malformed and unknown records retain their original bytes
when local records are edited. Local URI paths can contain raw Unix filename
bytes; labels use safe display captions. Changes replace the whole file atomically,
and read/save errors keep the previous shortcuts. Explorer refreshes external edits
about once a second; a label editor keeps its snapshot and rejects stale saves.
Independent applications can still race between the final recheck and replacement.
Symbolic-link bookmark files are readable but are not replaced. Files above 1 MiB,
more than 4096 local rows, or captions above 1024 bytes report a load/save error
instead of being truncated. Embedded NUL also rejects the whole file because
GTK would stop reading there.

Places also exposes Computer, the native XDG Desktop when present, Recent and
Trash, followed by Devices and Network. Only the activated sidebar row is
selected, including when a bookmark points to Home.
Mounted devices use GVolumeMonitor names, native root identities and GIcons.
Computer and Browse Network enumerate their actual GIO backends; Recent reads
GTK history while retaining each resource's original URI. Native virtual backends
activate on demand. Failed reads keep the previous route, listing and history;
missing services and authentication requirements report the native error.
URI locations participate in tabs, history and split panes. File operations and
clipboard exchange require actual local paths; they never treat a remote URI
as a local filename. URI completion, authenticated mounts and remote writes are
not implemented.

Drag a file (or the selection) out of the view to another application:
browsers' upload areas, Thunar or another file manager, the desktop and
editors receive it through XDND as `text/uri-list` file URIs (with the plain
paths as text). The drag starts after the pointer moves 8 pixels, so a plain
click still selects; copy, move and link are offered and Control, Shift and
Control+Shift choose one, as in GTK. Dropping on one of Explorer's folders,
Places or Tree rows, or on a pane's background, copies, moves or links there
with Thunar's rule: on the same filesystem an unmodified drag moves. Files
another application drops on the window go to the active folder.

Right-click a file, a selection, a folder, a folder's background, a Places row
or a Tree row (or press Shift+F10) for Thunar 4.20's context menu: the same
entries, order, enabled states and actions, including Open With and its
chooser, Send To, Create Document from Templates, custom actions from
`~/.config/Thunar/uca.xml`, the archive and wallpaper plugins' entries when
installed, Arrange Items and Zoom. `make test-context-menu` compares every case
with the installed Thunar's real menus; Configure Columns... and Expandable
Folders appear disabled because Explorer has neither feature yet, and Bulk
Rename... opens Thunar's renamer.

Places remains the default side pane. Tree opens the local Home/File System
tree; Ctrl+E toggles Tree visibility, and Ctrl+B toggles Places visibility.
Either shortcut switches to its pane when the other pane is visible
([Thunar bindings](https://raw.githubusercontent.com/xfce-mirror/thunar/master/thunar/thunar-window.c)).
Expand markers load one directory at a time. Folder labels open that folder,
including repeated clicks on the selected folder. Navigation reveals cwd's
ancestors. With Tree focused, arrows select/expand/collapse and Enter opens the
selected folder; Ctrl+1/2/3 returns keyboard navigation to the file view.
Deep selected folders reveal their marker and label automatically. When content
overflows, Left/Right buttons at the pane's bottom and Shift+wheel scroll
horizontally; manual scrolling persists until a navigation or reveal request.
Hidden applies to the tree too; a hidden cwd ancestor stays
visible. Refresh branch reloads the selected directory. Matching raw paths and
filesystem identities retain their expansion, selection and cached descendants.
Removed or replaced identities discard their old caches. Raw Unix names use
the same safe captions as the file views.

Reads are staged and checked before replacing a branch. Inaccessible or changing
directories, disappearing entries, symlink ancestor cycles and resource limits
report an error while retaining the prior branch. Limits are 4096 cached rows,
64 levels, 4095 path bytes and 65536 scanned entries per directory. The tree
does not watch filesystem changes automatically; refresh explicitly. Long labels
can be explored with horizontal scrolling. Tree rows accept dropped files.
Remote locations and devices remain pending; switching panes preserves bookmark records.

Copy, Cut and Paste (also Ctrl+C/X/V outside prompts) exchange local file
selections with desktop file managers on X11/XWayland. Explorer publishes both
`text/uri-list` and `x-special/gnome-copied-files`; URI-only lists copy, while
the GNOME header selects copy or cut. Spaces, Unicode and filename newlines
are percent-escaped. Remote URIs, invalid UTF-8/NUL, malformed or empty lists,
lists over 4096 files, and payloads over 1 MiB report an error before any
filesystem operation. Copy and cut retain every selected file, including
selections above 256 files, or fail without publishing a partial list.
The complete list is validated before paste; filesystem failures can leave a
completed prefix, with pending cut paths retained for retry.

Clipboard data remains owned by the copying application until another owner
replaces it or the application closes. A newer clipboard containing ordinary
text does not paste an older internal selection. Headless embeddings retain
the internal clipboard when native transport is unavailable. Explorer releases
only its own completed cut selection, never another application's clipboard.
For foreign cuts, Explorer remembers the exact owner/payload and completed paths
to prevent repeated moves. Re-copying identical bytes from the same foreign
owner window cannot be distinguished from retrying that cut; copy again with
a changed selection to reset it. Partial local cuts keep the original desktop
offer until completion; other applications may encounter already moved paths.
Native Wayland clipboard access and Wayland-native drag and drop are not implemented here.

List shows resizable Name, Size, Type and Date Modified columns. GTK measures
the headers and actual cell text; columns grow with their contents and Name
uses the remaining space. Manual widths remain caller-owned. Click a
header to sort; click again to reverse. Folders stay first in either direction.
Type displays GIO's localized MIME description, including native link metadata.
Size uses GLib's locale formatting. Dates follow Thunar's default: Today,
Yesterday, recent weekday names, then the locale date. Relative labels use the
installed Thunar translation catalog, and refresh when the local date changes.
The status bar follows Thunar's default directory and selection summaries,
including hidden-file totals, native plural translations, long byte sizes,
MIME descriptions and symbolic-link targets.
Equal metadata uses name and full-path ties so search results sort consistently.
Sorting and changing views preserve selected paths and reveal the focused item.
The declared `assets/` directory ships the canonical Kryon icon atlas. Native
builds and installs package it for use from any working directory. An embedding
host must ship `icons/ui.webp` under its own declared asset directory.

```sh
make build      # desktop profile
make check
make test       # filesystem model and embedded host, from source and saved IR
make test-ui    # desktop interaction on a private Xvfb display
make test-file-clipboard # native Explorer/Thunar interchange on a private desktop
make test-filenames # raw-byte names, directories and operations on a private desktop
make test-bookmarks # source/saved persistence and private GTK/sidebar GUI tests
make test-tree      # source/saved lazy tree, host integration and private GUI
make test-location  # source/saved paths, failure rollback, private Explorer/Thunar keys
make test-tabs      # dynamic state/real allocation failure and private native tabs
make test-split     # independent panes, real failures, native focus/drag and Thunar
make test-locations # fresh private GVfs/local backend, source/saved URI model tests
make test-thunar    # exact-pixel private comparison; writes differences and fails on mismatch
make benchmark-folder-opening # Explorer/Thunar startup and folder-opening latency
make test-native-theme # GTK bars/gestures, all views/split, full 4K/resize, source/saved
make test-native-status # installed Thunar footer oracle, locales and live metadata
make test-native-window # actual native cursors, themed window icon and scrollbar gestures
make test-window-lifecycle # source/saved close-all authentication and private window shortcuts
make test-interactions # real menu-hover, Delete/keypad, editor and window shortcuts
make test-context-menu # every context menu against the installed Thunar's (AT-SPI)
make test-drag-menu  # XDND drops on a probe, Thunar and Chromium; menu actions
make install
make test-installed
```

`scripts/ziran.sh` selects the compiler recorded in `ziran.lock`. If the
installed launcher predates this package format, select a current launcher
without replacing the installed one: `ZIRAN_LAUNCHER=/path/to/ziran make build`.
Use that setting for the other build and test commands as well. Local stack
development can instead use the ignored `ziran.local.toml` overrides described
in Ziran's package documentation; committed builds use the lock without them.

The desktop profile produces `build/explorer-desktop`. Its window and desktop entry
use GTK’s discovered `system-file-manager` icon. Native file chrome uses the
system arrow cursor; location editing retains the text cursor. File views use
GTK scrollbar geometry, input, overlay fading, theme assets, fonts and selection
metrics. Rounded native surfaces draw over their current background so Cairo
uses the same curve coverage as a GTK window. The application entry is the
Kryon `Frame` export in `src/app.zi`. The executable links the libraries
declared in `ziran.toml`, including
libxcb, GTK3, GIO, GObject, GLib, Pango, Cairo and GdkPixbuf. Package builds and
saved-IR executable builds propagate these native link requirements.
Filesystem access uses native Linux APIs. A portable ZX build needs a filesystem
host capability that is not currently available.
Current feature status and the remaining Thunar work are tracked in
`docs/THUNAR_PARITY.md`.
