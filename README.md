# Shelf

Shelf is the Linux file manager for Rill, written in Ziran with a Kryon user
interface. Its goal is full Thunar parity; the current implementation covers
basic navigation and file operations. It runs standalone and embeds directly
in Rill through its native Ziran host module.

Use the Icon, List and Compact buttons, or Ctrl+1, Ctrl+2 and Ctrl+3, to change
views. All views share selection, focus and sorting. Ctrl-click toggles a file;
Shift extends a range; Ctrl+Shift adds a range. Arrows follow the layout,
Home/End reach its ends, Ctrl moves focus without changing selection, Space
toggles selection and Enter opens the focused item. Double-click opens an item.

Images open in a large built-in preview. Use Fit, 100%, +/−, arrows and the
wheel to zoom or pan; Shift+wheel pans horizontally. Previous/Next or PgUp/PgDn
browse images. Open delegates to the desktop's default application; Esc closes
the preview. The Preview button or Ctrl+P also previews the focused file.
UTF-8 text previews read at most 64 KiB and scroll with arrows, Home/End,
PgUp/PgDn or the wheel. Other files show metadata and an Open action.

Common image files have thumbnails in the grid views. PNG, JPEG, WebP, GIF,
BMP, TIFF and SVG previews are tested with the native desktop backend; other
image formats depend on the installed Kryon codecs. Animated images show a
still frame. Missing, unreadable or undecodable files show an explicit message.

Shelf follows the configured desktop GTK palette, including light and dark
themes. Palette changes apply while Shelf is running. Views, icons, prompts
and previews share these colors; photographs keep their original colors.
Embedded drawing restores the caller's palette after each Shelf viewport.

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

The path bar uses clickable local breadcrumbs. Its Ancestors menu retains
hidden parents when the bar is narrow; clicking the current folder refreshes it.
The … button or Ctrl+L opens an inline location editor with the current path
selected. Enter opens a folder, or selects a regular file in its parent without
executing it. Escape cancels without changing the route, selection or history.
Relative paths resolve against the folder where editing started; `~` and `~/`
use Home. Input is literal: no shell evaluation, named-user expansion or remote
URI navigation; the editor accepts local path syntax. These local file/directory semantics follow
[current upstream Thunar's location entry](https://raw.githubusercontent.com/xfce-mirror/thunar/master/thunar/thunar-location-entry.c).
The installed Thunar 4.20.2 uses file launch instead; private native comparison
there covers completion keys and cancellation, while Shelf tests verify safe
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

The Places sidebar loads local shortcuts from `$XDG_CONFIG_HOME/gtk-3.0/bookmarks`
(or `$HOME/.config/gtk-3.0/bookmarks`). If that file is absent, it reads
`$HOME/.gtk-bookmarks`; the first edit writes the GTK3 location and leaves the
legacy file intact. Add current, Rename, Remove, Up and Down edit the selected
local bookmark and preserve its folder identity. The scrolling list opens a
bookmark on each click. Existing duplicate records are preserved; adding an
already-bookmarked folder selects its first record.

Storage follows the [GTK bookmark format](https://raw.githubusercontent.com/GNOME/gtk/gtk-3-24/gtk/gtkbookmarksmanager.c)
also used by [Thunar](https://raw.githubusercontent.com/xfce-mirror/thunar/master/thunar/thunar-shortcuts-model.c).
Unsupported remote, malformed and unknown records retain their original bytes
when local records are edited. Local URI paths can contain raw Unix filename
bytes; labels use safe display captions. Changes replace the whole file atomically,
and read/save errors keep the previous shortcuts. Shelf refreshes external edits
about once a second; a label editor keeps its snapshot and rejects stale saves.
Independent applications can still race between the final recheck and replacement.
Symbolic-link bookmark files are readable but are not replaced. Files above 1 MiB,
more than 4096 local rows, or captions above 1024 bytes report a load/save error
instead of being truncated. Embedded NUL also rejects the whole file because
GTK would stop reading there. Remote navigation and device shortcuts remain pending.

Places remains the default side pane. Tree opens the local Home/File System
tree; Ctrl+E switches between Tree and Places, and Ctrl+B returns to Places
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
can be explored with horizontal scrolling. Remote locations, devices and
drag/drop remain pending; switching panes preserves bookmark records.

Copy, Cut and Paste (also Ctrl+C/X/V outside prompts) exchange local file
selections with desktop file managers on X11/XWayland. Shelf publishes both
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
the internal clipboard when native transport is unavailable. Shelf releases
only its own completed cut selection, never another application's clipboard.
For foreign cuts, Shelf remembers the exact owner/payload and completed paths
to prevent repeated moves. Re-copying identical bytes from the same foreign
owner window cannot be distinguished from retrying that cut; copy again with
a changed selection to reset it. Partial local cuts keep the original desktop
offer until completion; other applications may encounter already moved paths.
Native Wayland clipboard access and drag/drop are not implemented here.

List shows resizable Name, Size (bytes), Type and Modified columns. Click a
header or the shared sort buttons to sort; click again to reverse. Folders
stay first in either direction. Type describes the filesystem kind, not MIME.
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
make test-file-clipboard # native Shelf/Thunar interchange on a private desktop
make test-filenames # raw-byte names, directories and operations on a private desktop
make test-bookmarks # source/saved persistence and private GTK/sidebar GUI tests
make test-tree      # source/saved lazy tree, host integration and private GUI
make test-location  # source/saved paths, failure rollback, private Shelf/Thunar keys
make install
make test-installed
```

The desktop profile produces `build/shelf-desktop`. The standalone entry is
the Kryon `Frame` export in `src/app.zi`. Rill imports `shelf/app_host` and calls
`Prepare`, `Draw` and `Close` with its session, viewport and focus state.
Keep each prepared `Host` at a stable address until `Close`.
Native embedding hosts using this clipboard adapter link libxcb (`-lxcb`).
Filesystem access uses native Linux APIs. A portable ZX build needs a filesystem
host capability that is not currently available.
Current feature status and the remaining Thunar work are tracked in
`docs/THUNAR_PARITY.md`.
