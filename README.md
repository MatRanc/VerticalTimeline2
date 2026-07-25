# VerticalTimeline

A Fusion 360 add-in that adds a vertical timeline. Works on Windows and macOS, though development and testing happen primarily on macOS.

<img src="screenshot-dark.png" width="170" alt="Vertical timeline (dark mode)">

The palette adapts to light and dark themes, following your operating system /
Fusion UI color theme.

## Installation

Download the add-in from the [Releases](https://github.com/MatRanc/VerticalTimeline2/releases) page.

Unpack it into `API\AddIns` (see [How to install an add-in or script in Fusion 360](https://knowledge.autodesk.com/support/fusion-360/troubleshooting/caas/sfdcarticles/sfdcarticles/How-to-install-an-ADD-IN-and-Script-in-Fusion-360.html)).

Make sure the directory is named `VerticalTimeline`, with no suffix.

Once installed, the timeline opens automatically whenever a Design is active.

## Usage

The timeline opens by itself. Closing it with its window *X* hides it for the
rest of the session; it comes back on the next Fusion start (or after
reloading the add-in). To turn it off for good, disable the add-in in the
*Scripts and Add-ins* dialog (*Shift+S*).

* Click an item to select it (this also selects it in the Fusion GUI).
* Double-click the name to rename it; double-click anywhere else on the row to
  edit the feature/part.
* Right-click an item for a context menu: *Roll Timeline Marker Here*, *Edit*,
  *Rename*, *Suppress*/*Unsuppress*, and *Delete*. For an item past the history
  marker (rolled back), the menu also offers *Delete all features after History
  Marker*. Right-clicking a sketch adds its native options too (*Show/Hide*,
  *Look At*, *Redefine*, display toggles, etc.).
* Drag the history-marker bar (the line between the active and rolled-back
  items) onto a row to roll the marker there, SolidWorks-style.
* *Cmd*/*Ctrl*-click (or *Shift*-click for a range) to select multiple items.
  The selection is pushed to Fusion as a real selection, so you can then run a
  command such as *Mirror* on those features. Right-click to *Create Group* or
  *Suppress*/*Delete* them together.

Selecting a feature in the Fusion GUI (in the native timeline or the browser)
also highlights the matching row in the timeline. Clicking *geometry* in the
viewport does not: Fusion reports the selection as a face/edge, and its API
exposes no way to find the feature that created it (see Known limitations).
Items that Fusion reports as errored or warned are highlighted red or yellow,
with the message shown on hover. A fully constrained sketch shows Fusion's own
lock-badge sketch icon.

The palette shows its own context menu rather than Fusion's native timeline
menu. Some native entries — *Create Selection Set*, *Configure*, *Find in
Browser*, *Find in Window* — have no add-in API to invoke, so they are not
included.

## Known limitations

* **Clicking geometry in the viewport does not highlight the creating
  feature's row** ([#14](https://github.com/MatRanc/VerticalTimeline2/issues/14)).
  Fusion's API gives no way to map a picked face/edge back to the feature
  that created it, and scanning every feature to find out would reintroduce
  the [#9](https://github.com/MatRanc/VerticalTimeline2/issues/9) freeze.
  Selecting the feature itself — a native-timeline row, or a
  sketch/plane/component in the browser — does highlight the row.

* **A few feature types show a generic placeholder icon instead of their real
  one** ([#8](https://github.com/MatRanc/VerticalTimeline2/issues/8)). Fusion
  sometimes hands a feature back with no concrete type information to pick an
  icon from (seen on some mesh, *Scale*, and *Modify* features; inconsistent —
  the same kind often comes through fine). No API workaround exists. Affected
  rows log `no icon resolved for feature type '…'` to the *Text Commands*
  console.

* **Some edits on large designs (roughly 1000+ timeline nodes) are still
  slow** ([#10](https://github.com/MatRanc/VerticalTimeline2/issues/10)).
  Reading the timeline has no bulk accessor (~6 ms/item), so a full re-read of
  a large design takes several seconds with Fusion frozen. Since v0.7.10 the
  common operations — roll, suppress/unsuppress, rename, sketch edits, and
  adds at the end — reuse cached timeline wrappers and refresh in ~0.25 s
  instead; deletes, mid-history inserts, reorders, undo/redo, and document
  switches still pay the full read (in theory, an unrecognized reorder could
  also show a stale row order — no known way to trigger it, and it
  self-heals). Details and the Autodesk API wishlist:
  [PERFORMANCE.md](docs/PERFORMANCE.md).

* **Deleting a group whose contents feed later features fails from the
  add-in** ([#25](https://github.com/MatRanc/VerticalTimeline2/issues/25)).
  The group-delete path calls `deleteMe()` directly instead of routing
  through Fusion's native Delete command the way ordinary deletes do
  ([#20](https://github.com/MatRanc/VerticalTimeline2/issues/20)), so it
  silently declines when a member has downstream dependents instead of
  showing Fusion's confirmation. Workaround: delete the group from Fusion's
  own timeline.

* **Deleting a rolled-back feature whose entity is an `Occurrence`** (e.g.
  *Create Components from Bodies*, *New Component*) **fails from the add-in**
  ([#24](https://github.com/MatRanc/VerticalTimeline2/issues/24)). A
  rolled-back row has no computed entity, so there's nothing valid to hand
  Fusion's selection/delete API — confirmed even a raw `TimelineObject` is
  rejected. Ordinary (non-`Occurrence`) rolled-back features delete fine.
  Workaround: delete it from Fusion's own native timeline. Wishlist for
  Autodesk: let the delete API accept an uncomputed/rolled-back entity.

## Changelog

Full history: [CHANGELOG.md](CHANGELOG.md).

## Credits

The original VerticalTimeline was created by **Thomas Axelsson**
([thomasa88](https://github.com/thomasa88)) and lives at
<https://github.com/thomasa88/VerticalTimeline>. All credit for that add-in goes
to the original author; this release builds on that work.

It uses [thomasa88lib](https://github.com/thomasa88/thomasa88lib), also by Thomas
Axelsson.

## License

This work is dual-licensed under **GPL-3.0-or-later OR MIT** &mdash; you may
choose either license. Copyright &copy; 2020 Thomas Axelsson. See
[LICENSE-GPL-3.0-or-later](LICENSE-GPL-3.0-or-later) and [LICENSE-MIT](LICENSE-MIT)
for the full texts. The original copyright and license notices are retained in
every source file.
