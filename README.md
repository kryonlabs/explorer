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
make install
make test-installed
```

The desktop profile produces `build/shelf-desktop`. The standalone entry is
the Kryon `Frame` export in `src/app.zi`. Rill imports `shelf/app_host` and calls
`Prepare`, `Draw` and `Close` with its session, viewport and focus state.
Keep each prepared `Host` at a stable address until `Close`.
Filesystem access uses native Linux APIs. A portable ZX build needs a filesystem
host capability that is not currently available.
Current feature status and the remaining Thunar work are tracked in
`docs/THUNAR_PARITY.md`.
