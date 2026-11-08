# Changelog

## [Unreleased]

- Add local split view with a native draggable divider, independent pane tabs
  and navigation state, explicit active-pane actions and a shared file clipboard.
  Collapsing retains both panes in memory; failed creation or re-enable preserves
  the usable pane and reports the error.

- Replace numbered tab controls with a native labeled strip, close buttons,
  scrolling overflow and drag/keyboard reorder. Dynamic tabs retain independent
  history, selection, focus, scrolling and view state; failed navigation keeps
  the previous usable tab and the last tab remains open.

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
- Added a locked Kryon desktop profile and direct native Ziran embedding for Rill.
- Removed the alternate build file, C sources, C host library and C tests.
- Documented the complete Thunar parity roadmap and current Rill hosting
  interface.
- Added model, embedded rendering and private desktop interaction tests.
