# Performance backlog

The standing TODO is "Improve performance further for very large files." This
file captures a prioritized, execution-ready list of optimizations. It is
documentation only — none of the items below are implemented yet.

Already shipped (v0.5.0): per-feature API-call dedup on the refresh path
(read `obj.entity`/`short_class` once, hoist `app.activeProduct` out of the
loop) and an O(1) GUI-selection highlight via an `entityToken → node id` index.
Those items are removed from the list below.

## Where the time goes

Every command completion calls `invalidate()` (`VerticalTimeline.py:307`), which:

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
   (`palette.html`) rebuilds every row from scratch and attaches ~6 event
   listeners per row, every refresh.

Common interactions (rolling the marker, renaming, selecting) all trigger the
full O(N) recompute + full DOM teardown even when the feature *list* is
unchanged.

## Tier 1 — biggest wins

1. **Skip per-feature work that didn't change (structure vs. state).** Split the
   payload into *structure* (feature list, type, image, parent-components —
   changes only on add/remove/reorder) and *state* (name, `isSuppressed`,
   `isRolledBack`, marker position — changes often). Cache structure keyed by a
   stable id and only recompute it when the timeline count/order changes.
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
   of ~6 `addEventListener` calls per row per rebuild. The handlers already use
   `closest` / target tests, so this is a natural refactor. File: `palette.html`
   `appendItems`.

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

- Add temporary timing around `invalidate()` and the JS render behind the
  existing `debug` flag (`run()`), open a large parametric design, and record
  ms/refresh before vs. after.
- Regression-check the interactions that share the refresh path: roll to a
  feature, rename, add/suppress a feature, collapse/expand groups, and GUI
  selection → row highlight — all must still behave as today.
</content>
