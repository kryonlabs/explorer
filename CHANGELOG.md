# Changelog

## [Unreleased]

- Build TaijiOS targets through the SDK's public Ziran exports, without adding
  dependency folders as module paths.

- Open TaijiOS PNG/JPEG files with the registered ZX image viewer.

- Drop the duplicate shot-only pixmap profile; screenshots use
  `kryon run desktop --png` from the desktop profile.

- Compose the Explorer interface in TSX: the application entry, tab strip,
  sidebar tree and places, breadcrumb and location editor, previews, dialogs,
  context menu, guest and controls views now live in `src/*.tsx` over the
  native `app_host` bridge, with no legacy `.zi` screen composition left.
  Item slices install from pane- and model-owned captions immediately before
  each TSX view and are emptied right after it returns.

## [0.1.0] - 2026-11-22

- Ship Explorer as a Linux amd64 Debian package and a ZX 28 application for TaijiOS.

- Run the shared Explorer frame and model in TaijiOS through typed guest
  filesystem and window adapters. Support location editing, navigation, sorting,
  scrolling, text preview, exclusive file and folder creation, regular-file copy,
  confirmed deletion, and window resizing with bounded listing and raster storage.
  Report unavailable guest operations explicitly.

- Open context menus without waiting for clipboard file data. Track offered
  formats asynchronously, including changes while a menu is open, and show
  actual application icons beside Open and Open With commands.
- Drag files out like Thunar: a primary-button drag past GTK's 8-pixel
  threshold offers the selection to other applications through XDND as
  `text/uri-list` (with plain-path text fallbacks), copy, move or link, with
  the file's icon under the pointer. Browsers' upload areas, Thunar and other
  file managers, the desktop and editors receive the files. Drops on
  Explorer's own folder rows, Places and Tree rows, or a pane's background
  copy, move or link them with Thunar's rule (same filesystem moves; Control
  copies, Shift moves, Control+Shift links). Files another application drops
  on the window go to the active folder.
- Right-click (or Shift+F10) opens Thunar 4.20's context menus, entry for entry
  and in Thunar's order: files, several files, folders, a folder's background
  in every view, Places rows and Tree rows. Open, Open With (the desktop's
  applications, Open With Other Application and Set Default Application), Send
  To (bookmarks, desktop links, mounted devices and Thunar's Send To
  handlers), Cut, Copy, Paste, Paste Into Folder, Move to Trash, Delete, Empty
  Trash, Rename, Restore, Remove from Recent, Create Folder, Create Document
  with the Templates folder, the configured custom actions (`uca.xml`), the
  archive and wallpaper plugins' entries, Arrange Items, Zoom and Properties
  follow Thunar's visibility and enabled rules and perform the same actions.
  The menus are drawn by GTK, including separators, radio and check rows and
  submenu arrows.
- Build against Kryon's per-widget packages (`kryon/box`, `kryon/text`, …)
  now that the `kryon/Widgets` facade is gone, and import the desktop host as
  `kryon/desktop_runtime`.
- Sort directory entries in O(n log n), size visible details before offscreen
  rows, and allocate file descriptions according to their text length. Submit
  completed location edits before drawing the destination.
- Benchmark icon and compact views as well as details against Thunar, set
  Thunar's view through its running settings daemon, count a folder as ready
  only once its entries are visible, and keep each first changed frame.

- Rename the package, executable, build output, desktop identity, embedded
  module paths and internal runtime names from Shelf to Explorer.
- Clarify Explorer as an independent standalone Thunar alternative and remove
  Rill hosting language from its public documentation.
- Add a private Xvfb Explorer/Thunar benchmark for fresh-window launch, first
  stable root rendering and tiny/medium/large folder-opening latency. Match
  details views, icon sizes and complete viewports, and time file-row changes
  separately from toolbar, status and scrollbar animations.
- Switch open menus on hover and support keyboard menu navigation with visible
  shortcuts. Apply native wheel distances immediately, handle keypad Delete,
  confirm permanent deletion, and preserve text-editor key behavior. Honor the
  normal arrow over disabled file-manager controls.
- Add view zoom, Help and read-only Properties, window/tab shortcuts and
  clipboard Insert aliases. Undo and redo retain complete operation batches,
  protect replacement objects and keep recovery data across history disposal.

- Use native GTK theme rendering, Pango fonts and discovered icon assets for
  Thunar-style menus, toolbar, location entry, Places sidebar, file views and
  status bar. Native scrollbar geometry, gestures and fading follow GTK.
- Discover devices and virtual locations through GIO, retain URI routes across
  tabs and panes, and report unavailable backends without losing the current
  directory. Format file metadata and status summaries with native locale data.

- Add local split view with a native draggable divider, independent pane tabs
  and navigation state, explicit active-pane actions and a shared file clipboard.
  Collapsing retains both panes in memory; failed creation or re-enable preserves
  the usable pane and reports the error.

- Replace numbered tab controls with a native labeled strip, close buttons,
  scrolling overflow and drag/keyboard reorder. Dynamic tabs retain independent
  history, selection, focus, scrolling and view state; failed navigation keeps
  the previous usable tab; closing the final tab closes the window.

- Add local breadcrumb navigation and an inline location editor with common-prefix
  completion, keyboard suggestions, literal relative/Home paths and lossless raw
  name editing. Failed or stale navigation retains the input, route and history;
  complete folder listings and active-tab paths commit together.

- Add a lazy local Tree side pane with cwd reveal, stable directory identities,
  hidden filtering, branch refresh and checked bounded reads that preserve good
  branches on errors and reject symbolic-link ancestor cycles.

- Add persistent editable local GTK bookmarks in Places, with add, label rename,
  removal, reordering, external refresh and preservation of unsupported records.
- Display Linux filenames with invalid UTF-8 using reversible byte escapes,
  preserving raw paths, selection identity and file operations across views,
  current paths, errors, previews and rename/location editors.
- Exchange desktop file copy/cut/paste selections with Thunar through native
  X11/XWayland MIME clipboard transport, including URI escaping, transactional
  payload validation, ownership changes and pending-cut retry handling.
- Follow the system GTK light/dark palette in views, icons, prompts and previews,
  refresh colors while running and preserve the embedding host's palette.
- Added image thumbnails and a large image preview with fit, actual size, zoom,
  panning, previous/next browsing and opening in the default desktop application.
- Added bounded UTF-8 text previews, file metadata and clear unavailable-preview
  messages, accessible through Preview or Ctrl+P.
- Added real Icon and Compact layouts using Kryon GridMulti and a details List
  using DataViews TableView, with shared selection, layout-aware navigation,
  scrolling, focus reveal, mode buttons and Ctrl+1/2/3.
- Added resizable Name, Size (bytes), filesystem Type and Modified columns and
  shared metadata sorting. Sorting preserves selected file identities, cursor
  and range anchor; deterministic ties and strict reversal keep folders first.
- Added bounded double-click and keyboard activation across all three views.
- Packaged the canonical icon atlas for native builds and installs, with readable
  foreground tint in both grid layouts.

- Replaced the legacy C application and build with a Linux-only Ziran model and
  Kryon UI.
- Preserved navigation history, tabs, selection, hidden-file filtering, recursive
  filename search, create/rename, copy/cut/paste, duplicate and symbolic links.
- Preserved XDG Trash metadata, deletion timestamps, collision-safe file/info names
  and restore support.
- Added visible tab switching, Trash restore controls and a native Ziran model
  test suite.
- Added a locked Kryon desktop profile and native Ziran application state.
- Removed the alternate build file, C sources, C host library and C tests.
- Documented the complete Thunar parity roadmap.
- Added model, embedded rendering and private desktop interaction tests.
