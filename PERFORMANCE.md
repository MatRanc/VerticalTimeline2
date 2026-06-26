# Performance backlog

The standing TODO is "Improve performance further for very large files." This
file captures a prioritized, execution-ready list of optimizations. It is
documentation only — none of the items below are implemented yet.

Already shipped (v0.5.0): per-feature API-call dedup on the refresh path
(read `obj.entity`/`short_class` once, hoist `app.activeProduct` out of the
loop) and an O(1) GUI-selection highlight via an `entityToken → node id` index.
Those items are removed from the list below.

## Considered and rejected: rewrite in C++

Fusion add-ins can be written in C++, but that won't speed this one up. Every slow
operation is an API call into Fusion's own compiled kernel (`obj.entity`, icon
resolution, timeline traversal) plus the HTML palette round-trip. A C++ add-in
calls the same API and waits on the same kernel and palette — it only saves Python
*dispatch* overhead (microseconds, against millisecond-plus API calls). Cost:
full ~1600-line rewrite, drop `thomasa88lib` (Python-only), per-platform compiles
(Windows + mac), and loss of Shift+S hot reload / `editEnabled` iteration. The real
lever is the Tier 1–3 items below.

## Where the time goes

Most command completions trigger `invalidate()` (`VerticalTimeline.py:307`) via
`command_terminated_handler`, which skips `SelectCommand`/`CommitCommand` and
non-completed terminations. `invalidate()`:

1. Re-reads the whole timeline and rebuilds the tree (`get_features` →
   `flatten_timeline` → `build_timeline_tree` → `get_component_parent_map` →
   `get_features_from_node`) — O(N) every refresh, even when the feature *list*
   is unchanged.
2. `get_features_from_node` (`VerticalTimeline.py:383`) still reads each
   feature's entity and rebuilds the full feature payload every refresh
   (structure + state together), so add/remove and a simple roll cost the same.
3. `get_component_parent_map` (`VerticalTimeline.py:560`) walks **all**
   occurrences every refresh, even though component structure rarely changes.
4. The palette JS then does `timeline.innerHTML = ''` and `appendItems`
   (`palette.html`) rebuilds every row from scratch and attaches ~7 event
   listeners per row, every refresh.

Rolling the marker and suppressing/unsuppressing leave the feature *list*
unchanged yet still trigger the full O(N) recompute + full DOM teardown (both
call `invalidate()`) — this is what Tier 1 #1/#2 target. Renaming already
updates the row in place, and GUI/palette selection uses the O(1) highlight
path shipped in v0.5.0; neither does a full rebuild.

## Tier 1 — biggest wins

1. **Skip per-feature work that didn't change (structure vs. state).** Split the
   payload into *structure* (feature list, type, image, parent-components —
   changes only on add/remove/reorder) and *state* (name, `isSuppressed`,
   `isRolledBack`, marker position — changes often). Caveat: an occurrence's
   `parent-components` collapses to `[]` while it is rolled back/suppressed
   (`get_feature_parent_path`), so it's not purely structural. Cache structure
   keyed by a stable id and only recompute it when the timeline count/order
   changes.
   Re-read only the volatile state on a normal refresh. Files: `get_features` /
   `get_features_from_node` / `invalidate`
   (`VerticalTimeline.py:307,372,383`).

2. **Don't full-rebuild on marker-only (roll) changes.** Rolling the marker
   (right-click → roll) leaves the feature list identical; only which rows are
   "rolled back" changes. When `timeline.count` is unchanged but `markerPosition`
   changed, send a lightweight message (new marker / set of rolled-back ids) and
   have the JS toggle the `suppressed` / `first-rolled-back` classes in place
   instead of `innerHTML=''` + full rebuild. Files: `invalidate`,
   `command_terminated_handler`, `rollToFeature` handler; `palette.html`
   `handle()` (add a `setMarker` action).

## Tier 2 — server-side, low risk

3. **Cache `get_component_parent_map()` across refreshes.** Recompute only when
   the structure likely changed (e.g. when `timeline.count` changes), instead of
   walking all occurrences every refresh. Secondary: weigh staleness vs. cost.
   File: `VerticalTimeline.py:560`.

## Tier 3 — palette rendering

4. **Event delegation.** Attach `click` / `dblclick` / `contextmenu` once on the
   `#timeline` container and dispatch via `e.target.closest('.feature')`, instead
   of re-attaching those three to every row on every rebuild. (That removes 3 of
   the ~7 listeners a row gets; the 4 name-field listeners are a separate
   concern.) These handlers already use `closest` / target tests, so this is a
   natural refactor. File: `palette.html` `appendItems`.

5. **In-place updates instead of full teardown** for state-only refreshes (ties
   to #1/#2): toggle classes and set names on existing rows; keep full rebuild
   only when the feature set actually changes (consider keyed diffing later).
   File: `palette.html`.

6. **Coalesce/debounce `invalidate()`.** `command_terminated_handler` can fire in
   bursts; defer + collapse rapid invalidations into one refresh (Fusion pattern:
   post a custom event + pending flag — note the existing "cannot sendInfoToHTML
   inside the event handler" constraint). Medium complexity; optional. Files:
   `command_terminated_handler`, `invalidate`.

## Recommended order

#3 (safe, immediate) → #1, #2, #5 (structure/state + incremental render, the
largest win) → #4, #6.

## How to verify the work when it's done

- Add temporary timing around `invalidate()` and the JS render — gate it on the
  `debug` flag in `run()` (currently declared but unused, so wire it up first),
  open a large parametric design, and record ms/refresh before vs. after.
- Regression-check the interactions that share the refresh path: roll to a
  feature, rename, add/suppress a feature, collapse/expand groups, and GUI
  selection → row highlight — all must still behave as today.
