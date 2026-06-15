# VerticalTimeline

A Fusion 360 add-in that adds a vertical timeline. Works on Windows and macOS.

<img src="screenshot-dark.png" width="170" alt="Vertical timeline (dark mode)">

The palette adapts to light and dark themes, following your operating system /
Fusion UI color theme.

## Installation

Download the add-in from the [Releases](https://github.com/MatRanc/VerticalTimeline2/releases) page.

Unpack it into `API\AddIns` (see [How to install an add-in or script in Fusion 360](https://knowledge.autodesk.com/support/fusion-360/troubleshooting/caas/sfdcarticles/sfdcarticles/How-to-install-an-ADD-IN-and-Script-in-Fusion-360.html)).

Make sure the directory is named `VerticalTimeline`, with no suffix.

## Usage

The timeline is shown using *File* -> *View* -> *Toggle Vertical Timeline*.

* Click an item to select it.
* Double-click on an item to edit it.
* Click on an item text to rename it.
* Right-click an item for a context menu: *Roll Timeline Marker Here*, *Edit*,
  *Rename*, *Suppress*/*Unsuppress*, and *Delete*.
* *Cmd*/*Ctrl*-click (or *Shift*-click for a range) to select multiple items,
  then right-click to *Create Group* or *Suppress*/*Delete* them together.

Selecting a feature in the Fusion GUI also highlights the matching row in the
timeline.

The palette shows its own context menu rather than Fusion's native timeline
menu. Some native entries — *Create Selection Set*, *Configure*, *Find in
Browser*, *Find in Window* — have no add-in API to invoke, so they are not
included.

The add-in can be temporarily disabled using the *Scripts and Add-ins* dialog. Press *Shift+S* in Fusion 360™ and go to the *Add-Ins* tab.

## TODO

* Improve performance further for very large files.

## Changelog

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
* v 0.2.1
  * Enable *Run on Startup* by default.
* v 0.2.0
  * Fix selection of features inside components/occurrences.
  * Allow selection of rolled back and suppressed features.

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
