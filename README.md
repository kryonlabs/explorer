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
