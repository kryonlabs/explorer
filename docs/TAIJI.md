# Explorer on TaijiOS

The ZX target uses Explorer's existing `App.Frame`, model, location editor,
selection, and preview. The Taiji host supplies the window and renders that
frame through Kryon. Explorer starts in the guest Home directory, then tries
the guest working directory and `/`. All paths and file actions go through the
Taiji namespace and its permissions.

The guest host receives opaque rows through its typed surface API and presents
them once the frame is complete. Explorer reuses up to 128 KiB for raster
and upload strips as the window changes size. The ZX build selects Kryon's
external-buffer pixmap profile to avoid allocating another full raster. After
input settles, composition sleeps until the next window or input event.

Build against the Taiji SDK package exports and Kryon `host/surface` export.
Local Ziran, Kryon and `taiji_sdk` development overrides belong in the ignored
`ziran.local.toml`; set `taiji_sdk` to the canonical TaijiOS checkout.

```sh
make taiji
make test-guest-files
make test-taiji-model
make test-taiji-desktop
```

`make taiji` writes `build/explorer.zx`. For guest tests with a different canonical
checkout location, set `TAIJIOS_ROOT` when invoking `make`. `test-taiji-model` runs that
model inside a real Taiji emulator with the standard 32 MiB heap. It uses only
its disposable guest Home fixture and tests UTF-8 paths, bounded navigation
history, exclusive creation, copy collisions, preview, and deletion. It also
sorts a 1,024-entry folder and verifies that an oversized listing keeps the
previous folder visible. The portable provider tests simulate malformed
records and short writes.

`test-taiji-desktop` uses a private Xvfb display and an owned guest fixture to
exercise browsing, file actions, growing and shrinking the window, repeated
navigation, and clean close under the same heap limit. Set
`EXPLORER_TAIJI_ROWS=1024` to exercise a 1,027-entry directory and
`EXPLORER_TAIJI_REPORT_MEMORY=1` to report the guest allocator's high-water
mark after close. It requires Pillow, Tesseract, ImageMagick, and xdotool.
Both guest tests use the Taiji checkout's `emu/Linux/o.emu` by default.
Set `TAIJIOS_EMULATOR` to the path of an installed emulator to test it instead.

The list supports selection, sortable columns, wheel and keyboard scrolling. Use the
path bar or Ctrl+L to edit a location, and Enter or Open to open a folder or
preview a file. The Actions menu creates folders and empty files, copies
regular files, and confirms permanent deletion. Copying is exclusive at the
destination. Failed copy cleanup checks that the destination still names the
created file before attempting removal. Guest devices control whether an
empty directory can be removed.

Taiji currently lacks a default-app dispatcher and a no-replace rename API.
Explorer can preview UTF-8 text and show file metadata. Rename, move, recursive
copy, Trash, and desktop associations are unavailable in the guest.

Paths are limited to 4,095 bytes and names to 255 bytes. Explorer reads
packed directory records through an 8 KiB buffer and retains at most 4,096
entries and 1 MiB of path text per listing. Failed or oversized reads preserve
the current listing. The back and forward histories each hold up to 64 paths
within 8 KiB. Regular-file copy streams up to 16 MiB in 8 KiB chunks. Text
preview reads up to 64 KiB, with up to four extra bytes to check the UTF-8
boundary.
