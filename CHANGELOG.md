# Changelog

* v 0.7.10
  * Investigated [#24](https://github.com/MatRanc/VerticalTimeline2/issues/24)
    (deleting a rolled-back feature): the #20 native-delete change above
    already fixed the crash for the common cases. The remaining gap - a
    rolled-back `Occurrence` row (e.g. *New Component*) can't be selected for
    delete via the scripting API at all - is a hard API wall, not a bug; see
    *Known limitations*. The "Could Not Delete" popup now says so when it
    applies, instead of a bare "could not delete this."
  * Deleting a feature that later features depend on now hands off to
    Fusion's own *Delete* command instead of calling the API's `deleteMe()`
    directly, so it shows Fusion's own accurate "Permanently delete these
    features and all features that reference them?" confirmation and performs
    the correct cascading delete - instead of failing with a raw, misleading
    error dump, or a custom warning built from an approximation of Fusion's
    dependency graph that the API can't fully see
    ([#20](https://github.com/MatRanc/VerticalTimeline2/issues/20)).
  * Right-clicking a feature in Fusion's own context menu (native Timeline or
    browser tree) now offers *Find in Vertical Timeline*, which selects and
    scrolls to that row in the palette
    ([#23](https://github.com/MatRanc/VerticalTimeline2/issues/23)). Most
    reliable from the Timeline bar and browser tree; viewport right-clicks
    only work when the picked entity itself maps to a timeline row (not a
    bare face/edge, which has no single owning feature).
  * *Review warning* now opens a panel showing the warning text client-side,
    instead of trying (and failing) to run a native "Review warning" command
    that doesn't exist via the API
    ([#17](https://github.com/MatRanc/VerticalTimeline2/issues/17)). Also
    cleans up the raw HTML markup and un-separated multi-item text Fusion's
    warning messages can contain.
  * Fixed *Manage Lost Projections* showing for any sketch warning, not just
    an actual lost projection
    ([#18](https://github.com/MatRanc/VerticalTimeline2/issues/18)). It's now
    gated on the warning text actually describing a lost projection source,
    rather than a `SketchEntity.referencedEntity is None` check that turned
    out unreliable - Fusion substitutes a cached, still-valid reference even
    when the source is genuinely lost.
  * Fixed the history-marker bar going stale (not moving) when a group was
    collapsed or expanded, including via the new *Collapse All*/*Expand All*
    buttons; it also no longer snaps to the top of the palette when the
    rollback point is inside a collapsed group.
  * New *Collapse All* / *Expand All* buttons above the timeline collapse or
    expand every group in one click
    ([#21](https://github.com/MatRanc/VerticalTimeline2/issues/21)).
  * Fixed several timeline items that couldn't be edited, or crashed, because
    their edit-command id was wrong or missing: construction planes (all 8
    ids were guessed and didn't exist, so editing one crashed with
    `AttributeError`, [#15](https://github.com/MatRanc/VerticalTimeline2/issues/15))
    and Emboss (had no edit command, so editing it silently did nothing,
    [#16](https://github.com/MatRanc/VerticalTimeline2/issues/16)). Rule Fillet, solid Delete Face, Derive, and
    Construction Axis/Point - previously icon-only - are now editable too.
    All ids are now verified against a running Fusion session instead of
    guessed.
  * Hardened the undo/redo full-refresh guard to also cover the Undo/Redo
    dropdown menu items, not just the plain undo/redo commands, so a reorder
    undone that way can't slip through with a stale row order.
  * Large-design refreshes are ~25× faster for the common operations. The
    palette now reuses the timeline wrappers from the previous refresh
    whenever a cheap validation shows the feature set is unchanged (or only
    grew at the end), instead of re-reading the whole timeline object by
    object. Rolling the marker (from either timeline), suppress/unsuppress,
    rename, sketch edits, and adds at the end (extrude etc.) refresh in
    ~0.25 s instead of ~6.4 s on a 1054-slot design (measured live). The cache
    holds live object references and all row state is re-read each refresh, so
    reused rows never show outdated data. Deletes, middle-of-history inserts,
    reorders, undo/redo, and document switches still do the full re-read
    ([#10](https://github.com/MatRanc/VerticalTimeline2/issues/10)).
  * Rolling the history marker from the palette (right-click → *Roll Timeline
    Marker Here*, or dragging the marker bar) no longer rebuilds the whole
    palette. The rolled-back rows are computed from the cached timeline and
    updated in place, and the `FusionRollCommand` the roll itself fires no
    longer triggers a follow-up full rebuild (rolls made on Fusion's native
    timeline still refresh normally). Any remaining wait on a palette roll is
    Fusion's own recompute of the design
    ([#10](https://github.com/MatRanc/VerticalTimeline2/issues/10)).
  * The component parent map behind the colored parent bars is cached across
    refreshes and rebuilt when the timeline count or document changes, instead
    of walking every occurrence on each refresh. Renaming or reparenting a
    component may show stale bars until the next add/delete
    ([#10](https://github.com/MatRanc/VerticalTimeline2/issues/10)).
  * Palette row events (click / double-click / context menu) are attached once
    to the timeline container instead of three listeners per row on every
    rebuild ([#10](https://github.com/MatRanc/VerticalTimeline2/issues/10)).
* v 0.7.9
  * Fixed the stutter when dragging/rotating a jointed component. Each drag
    release fires `FusionDragComponentsCommand`, which is kinematic and never
    changes the timeline, but it was triggering a full palette rebuild anyway;
    it's now skipped like the other selection/commit chatter.
* v 0.7.8
  * The palette is now shown by default. Fresh installs auto-show the timeline;
    existing users keep whatever they last chose. Closing it with the window X
    hides it for the session only - it returns on the next Fusion start or
    add-in reload. To turn the add-in off for good, use Fusion's
    Scripts and Add-Ins dialog (Shift+S)
    ([#11](https://github.com/MatRanc/VerticalTimeline2/issues/11)).
  * Removed the redundant Toggle menu item - the palette's own show/hide now
    covers it ([#11](https://github.com/MatRanc/VerticalTimeline2/issues/11)).
  * Selection highlighting is now driven by the feature's timeline position
    instead of a per-feature entity scan, so highlighting a selected row is
    faster and more reliable on large designs
    ([#14](https://github.com/MatRanc/VerticalTimeline2/issues/14)).
  * Mesh-editing features (from the ParaMesh tree) now show their real icons
    instead of the generic placeholder.
* v 0.7.7
  * Deleting a broken/yellow *Create Components from Bodies* row now removes it
    instead of failing (it previously tried to remove the component). The
    delete-recovery that already handled *suppressed* such rows now also covers
    rows in an error/warning state.
  * *Delete group and its contents* no longer silently does nothing. It now
    removes each contained feature individually and, when Fusion refuses to
    delete one because it has downstream dependents, reports that instead of
    freezing and quietly leaving the group in place. Deleting a group whose
    contents feed later features is still a Fusion API limitation (the scripting
    API can't show the "may cause downstream issues" confirmation that the native
    timeline uses to force such deletes) - use the native timeline delete for
    those. Individual deletes are also slower on large groups and take multiple
    undo steps, since the API can't batch them atomically.
* v 0.7.6
  * Emboss, Derive, Rule Fillet, solid Delete Face, and Construction Axis/Point
    now show their real icon instead of the generic placeholder.
  * Reduced remaining camera-navigation stutter on Windows: orbit/pan/zoom
    commands are now skipped by their resource type, not just a fixed list of
    ids (which varies by build), so a navigation command never triggers a
    timeline rebuild ([#9](https://github.com/MatRanc/VerticalTimeline2/issues/9)).
  * Still-unmapped feature icons (sheet-metal, mesh-editing, and volumetric
    features) remain a known gap.
* v 0.7.5
  * Fixed a multi-second freeze when starting a camera pan/orbit in large
    assemblies. The GUI-selection row highlight was running a per-feature lookup
    scan on every viewport selection; large timelines now match via the fast
    index only and skip the scan ([#9](https://github.com/MatRanc/VerticalTimeline2/issues/9)).
  * Redundant timeline refreshes from rapid command bursts are coalesced into a
    single refresh.
  * Timeline refresh is faster on large designs: the timeline is now read by
    index (`.item(i)`) instead of Python iteration, trimming ~30% off the
    timeline walk (~8.8s -> ~5.8s on a 1452-node design). Both timelines and
    groups behave identically ([#10](https://github.com/MatRanc/VerticalTimeline2/issues/10)).
* v 0.7.4
  * The timeline now keeps its scroll position per document, so switching files
    (and plain refreshes) returns you to where you were instead of the top.
  * Sketch rows gain the native right-click actions (Edit Sketch, Redefine
    Sketch Plane, and related items) in the timeline menu
    ([#6](https://github.com/MatRanc/VerticalTimeline2/issues/6), [#7](https://github.com/MatRanc/VerticalTimeline2/issues/7)).
  * Fixed missing/placeholder icons for several timeline features
    ([#8](https://github.com/MatRanc/VerticalTimeline2/issues/8)).
  * Selecting or deleting a suppressed *Body -> Component* feature from the
    timeline no longer fails.
  * The *Group Delete* popup can delete the group together with its contents
    without throwing ([#5](https://github.com/MatRanc/VerticalTimeline2/issues/5)).
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
