# VerticalTimeline

A Fusion 360 add-in that adds a vertical timeline. Works on Windows and macOS, though development and testing happen primarily on macOS.

<img src="screenshot-dark.png" width="170" alt="Vertical timeline (dark mode)">

The palette adapts to light and dark themes, following your operating system /
Fusion UI color theme.

## Installation

Download the add-in from the [Releases](https://github.com/MatRanc/VerticalTimeline2/releases) page.

Unpack it into `API\AddIns` (see [How to install an add-in or script in Fusion 360](https://knowledge.autodesk.com/support/fusion-360/troubleshooting/caas/sfdcarticles/sfdcarticles/How-to-install-an-ADD-IN-and-Script-in-Fusion-360.html)).

Make sure the directory is named `VerticalTimeline`, with no suffix.

Once installed, turn the timeline on with *File* -> *View* -> *Toggle Vertical Timeline*.

## Usage

The timeline is shown using *File* -> *View* -> *Toggle Vertical Timeline*.

* Click an item to select it (this also selects it in the Fusion GUI).
* Double-click the name to rename it; double-click anywhere else on the row to
  edit the feature/part.
* Right-click an item for a context menu: *Roll Timeline Marker Here*, *Edit*,
  *Rename*, *Suppress*/*Unsuppress*, and *Delete*. For an item past the history
  marker (rolled back), the menu also offers *Delete all features after History
  Marker*. Right-clicking a sketch adds its native options — *Show/Hide*,
  *Look At*, *Redefine*/*Select Sketch Plane*, *Configure*, and the *Profile* /
  *Dimension* / *Projected* / *Construction* display toggles.
* Drag the history-marker bar (the line between the active and rolled-back
  items) onto a row to roll the marker there, SolidWorks-style.
* *Cmd*/*Ctrl*-click (or *Shift*-click for a range) to select multiple items.
  The selection is pushed to Fusion as a real selection, so you can then run a
  command such as *Mirror* on those features. Right-click to *Create Group* or
  *Suppress*/*Delete* them together.

Selecting a feature in the Fusion GUI also highlights the matching row in the
timeline. Items that Fusion reports as errored or warned are highlighted red or
yellow, with the message shown on hover. A fully constrained sketch shows
Fusion's own lock-badge sketch icon.

The palette shows its own context menu rather than Fusion's native timeline
menu. Some native entries — *Create Selection Set*, *Configure*, *Find in
Browser*, *Find in Window* — have no add-in API to invoke, so they are not
included.

The add-in can be temporarily disabled using the *Scripts and Add-ins* dialog. Press *Shift+S* in Fusion 360™ and go to the *Add-Ins* tab.

## Known limitations

* **A few feature types show a generic placeholder icon instead of their real
  one** ([#8](https://github.com/MatRanc/VerticalTimeline2/issues/8)). Fusion's
  API hands some features back only as the generic base `Feature` class — with
  no concrete subclass and no other type information — so the add-in cannot tell
  what they are in order to pick an icon. Observed so far: base mesh features,
  some *Scale* features, and *Modify* features. (Note Fusion is inconsistent:
  the *same* feature kind sometimes comes through with its real type, so most
  rows do get the correct icon.) There is no API workaround; the issue is left
  open in case a future Fusion release exposes the type.

## TODO

* Improve performance further for very large files. See
  [PERFORMANCE.md](PERFORMANCE.md) for the prioritized backlog.

## Changelog

* v 0.7.4
  * The timeline now keeps its scroll position per document, so switching files
    (and plain refreshes) returns you to where you were instead of the top.
  * Sketch rows gain the native right-click actions (Edit Sketch, Redefine
    Sketch Plane, and related items) in the timeline menu (#6, #7).
  * Fixed missing/placeholder icons for several timeline features (#8).
  * Selecting or deleting a suppressed *Body -> Component* feature from the
    timeline no longer fails.
  * The *Group Delete* popup can delete the group together with its contents
    without throwing (#5).
  * Occurrence rows show the correct pin, cut-paste, and body-to-component icons.
* v 0.7.3
  * The *Toggle Translucency* context-menu item is now *Change Transparency
    (50% / 100%)* with a cube icon, matching the standalone ChangeTransparency
    add-in.
  * Rolling the history marker onto an item inside a collapsed group now lands on
    that item (the group auto-expands) instead of redirecting the roll to the
    whole group.
  * Selecting a grouped feature in Fusion now reliably highlights its timeline
    row, even when Fusion's entity token differs between refresh and selection.
* v 0.7.2
  * Browser icons load Fusion's high-resolution (2x) artwork, so they are crisp
    on Retina/HiDPI displays instead of blurry.
  * Icons now follow the palette's light/dark theme: each icon uses Fusion's
    light-foreground (`-dark`) artwork on a dark palette and the normal artwork
    on a light palette, so details like the extrude arrow stay visible either way.
* v 0.7.1
  * The right-click *Delete* and *Delete all features after History Marker* items
    show the red Delete icon again.
  * *Roll Timeline Marker Here* now shows its proper timeline-marker glyph instead
    of the roll-forward arrow.
  * Long context-menu items (e.g. *Delete all features after History Marker*) wrap
    instead of stretching the menu across the whole panel.
  * Added [docs/ICONS.md](docs/ICONS.md) documenting how Fusion's icon resources
    are resolved (the Fusion vs Neutron trees and the macOS/Windows path split).
* v 0.7.0
  * Draggable history-marker bar: drag the marker (the silver line with the grip
    on the right, between the active and rolled-back items) onto a row to roll
    the marker there, SolidWorks-style.
  * New *Toggle Translucency* context-menu item makes a feature's bodies 50%
    translucent (and back), like Fusion's *Opacity Control*.
  * Fully constrained sketches now show Fusion's own lock-badge sketch icon.
  * Fixed the sheet-metal component icon (it had been showing the generic
    placeholder); the add-in can now load Fusion's SVG-only icons too.
* v 0.6.0
  * Fixed group collapse: only the last group's collapse toggle used to work.
  * Rolled-back items now offer *Delete all features after History Marker* in
    the right-click menu.
  * Double-click the name to rename; double-click elsewhere on the row to edit.
    A single click now selects (and selects the feature in the Fusion GUI too).
  * Multi-selected rows are pushed to Fusion as a real selection, so commands
    such as *Mirror* can consume the picked features.
  * Errored/warned items are highlighted red/yellow, with the message on hover.
  * Fixed a crash when selecting a position Snapshot.
* v 0.5.0
  * Performance: highlighting the timeline row for the feature selected in the
    GUI is now a direct lookup instead of scanning every timeline item on each
    selection change, so large designs no longer stutter on each click.
  * Performance: the palette refresh now reads each feature's data once instead
    of making several redundant Fusion API calls per feature.
* v 0.4.1
  * Fixed a crash (error dialog) when closing a pure assembly file, caused by
    reading a construction plane's definition while the document was being torn
    down.
  * Fixed a crash (`KeyError`) when removing a component, caused by the timeline
    still referencing the component after the parent-component map had been
    rebuilt without it.
  * Hardened the palette refresh and click handlers so a design that is
    momentarily out of sync (during a file close or a mutating command) no
    longer produces a traceback dialog.
* v 0.4.0
  * New right-click context menu on timeline items: *Roll Timeline Marker Here*,
    *Edit*, *Rename*, *Suppress*/*Unsuppress*, and *Delete*. Right-clicking no
    longer rolls the marker automatically.
  * Select multiple rows (*Cmd*/*Ctrl*-click to toggle, *Shift*-click for a
    range) and *Create Group* from the selection, plus bulk
    *Suppress*/*Unsuppress*/*Delete*.
  * Menu items show Fusion's own icons where available.
  * Removed the version number from the palette title.
* v 0.3.0
  * Updated for the latest Fusion. The palette now uses the new (Qt) web
    browser instead of the deprecated CEF browser, with the matching async
    `adsk.fusionSendData` handling. Verified against Fusion's Python 3.12
    runtime.
  * Dark mode support. The palette follows the OS / Fusion UI color theme via
    the `prefers-color-scheme` media query.
  * Fixed a startup error (`InternalValidationError : pActiveEnvironment`)
    caused by reading the active workspace before Fusion had an active
    environment (e.g. on the Home screen).
  * Fixed a crash (`Associated feature is invalid`) when clicking or renaming a
    timeline group; groups and entity-less items are now handled gracefully.
  * Correctly select and edit primitive features (e.g. *Box*, *Cylinder*)
    inside components by selecting the feature proxy rather than its bodies.
  * Highlight the timeline row matching the feature selected in the Fusion GUI.
  * Component coloring is now derived from the component name, so colors stay
    consistent across timeline refreshes and across documents.
  * Replaced blocking error message boxes with non-intrusive, auto-clearing
    status messages in the palette.
  * More robust occurrence-type detection (handles component names containing
    spaces).
  * Cache resolved feature-icon paths to avoid a filesystem check per feature
    on every refresh.
  * Map *Move*/*Align* features so they get a proper icon and become editable
    on Fusion versions that expose their entity.

## Credits

VerticalTimeline was created by **Thomas Axelsson**
([thomasa88](https://github.com/thomasa88)). The original project lives at
<https://github.com/thomasa88/VerticalTimeline>. All credit for the add-in goes
to the original author; this release builds on that work.

It uses [thomasa88lib](https://github.com/thomasa88/thomasa88lib), also by Thomas
Axelsson.

## License

This work is dual-licensed under **GPL-3.0-or-later OR MIT** &mdash; you may
choose either license. Copyright &copy; 2020 Thomas Axelsson. See
[LICENSE-GPL-3.0-or-later](LICENSE-GPL-3.0-or-later) and [LICENSE-MIT](LICENSE-MIT)
for the full texts. The original copyright and license notices are retained in
every source file.
