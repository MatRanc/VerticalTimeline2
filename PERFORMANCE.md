# Performance backlog

The standing TODO is "Improve performance further for very large files." This
file captures a prioritized, execution-ready list of optimizations. It is
documentation only — none of it is implemented yet.

## Where the time goes

Every command completion calls `invalidate()` (`VerticalTimeline.py:251`), which:

1. Re-reads the whole timeline and rebuilds the tree (`get_features` →
   `flatten_timeline` → `build_timeline_tree` → `get_component_parent_map` →
   `get_features_from_node`).
2. For **every** feature, `get_features_from_node` (`VerticalTimeline.py:320`)
   makes ~8–15 Fusion API round-trips: `obj.entity` is fetched 3–4 separate
   times (in the try-block, in `short_class(obj.entity)`, again inside
   `get_feature_image` → `get_feature_res`, and again inside
   `get_feature_parent_path`), `short_class` is recomputed each time, and
   `get_feature_parent_path` (`VerticalTimeline.py:382`) reads `app.activeProduct`
   once per feature. API marshalling is the dominant cost.
3. `get_component_parent_map` (`VerticalTimeline.py:462`) walks **all**
   occurrences every refresh, even though component structure rarely changes.
4. The palette JS then does `timeline.innerHTML = ''` and `appendItems`
   (`palette.html`) rebuilds every row from scratch and attaches ~6 event
   listeners per row, every refresh.
5. `active_selection_changed_handler` (`VerticalTimeline.py`) loops over **all**
   timeline nodes and does a per-node `obj.entity` access on every GUI selection
   change — O(N) API calls per click.

Common interactions (rolling the marker, renaming, selecting) all trigger the
full O(N) recompute + full DOM teardown even when the feature *list* is
unchanged.

## Tier 1 — biggest wins

1. **Skip per-feature work that didn't change (structure vs. state).** Split the
   payload into *structure* (feature list, type, image, parent-components —
   changes only on add/remove/reorder) and *state* (name, `isSuppressed`,
   `isRolledBack`, marker position — changes often). Cache structure keyed by a
   stable id (`entity.entityToken`, computed once per feature) and only recompute
   it when the timeline count/order changes. Re-read only the volatile state on a
   normal refresh. Eliminates most of the ~8–15 API calls/feature on the common
   path. Files: `get_features` / `get_features_from_node` / `invalidate`
   (`VerticalTimeline.py:251,311,320`).

2. **Don't full-rebuild on marker-only (roll) changes.** Rolling the marker
   (right-click → roll) leaves the feature list identical; only which rows are
   "rolled back" changes. When `timeline.count` is unchanged but `markerPosition`
   changed, send a lightweight message (new marker / set of rolled-back ids) and
   have the JS toggle the `suppressed` / `first-rolled-back` classes in place
   instead of `innerHTML=''` + full rebuild. Files: `invalidate`,
   `command_terminated_handler`, `rollToFeature` handler; `palette.html`
   `handle()` (add a `setMarker` action).

3. **O(1) selection highlight via a prebuilt index.** Build an
   `entityToken → node id` map once when the tree is built; in
   `active_selection_changed_handler` map each selected entity's token and look it
   up, instead of scanning all nodes and touching `obj.entity` per node on every
   click. Files: `build_timeline_tree` / `get_features`,
   `active_selection_changed_handler`.

## Tier 2 — server-side, low risk

4. **Dedupe Fusion API round-trips per feature.** Read `entity = obj.entity` once
   and thread it into `get_feature_image` / `get_feature_res` /
   `get_feature_parent_path` (add an `entity=` param); compute `short_class` once
   and reuse. Roughly halves API calls per feature, no behavior change. Files:
   `get_features_from_node`, `get_feature_res`, `get_feature_image`,
   `get_feature_parent_path` (`VerticalTimeline.py:209,187,382`).

5. **Hoist `app.activeProduct` out of the per-feature loop.** It's fetched once
   per feature in `get_feature_parent_path`; read it once per `get_features` and
   pass it down. File: `VerticalTimeline.py:382`.

6. **Cache `get_component_parent_map()` across refreshes.** Recompute only when
   the structure likely changed (e.g. when `timeline.count` changes), instead of
   walking all occurrences every refresh. Secondary: weigh staleness vs. cost.
   File: `VerticalTimeline.py:462`.

## Tier 3 — palette rendering

7. **Event delegation.** Attach `click` / `dblclick` / `contextmenu` once on the
   `#timeline` container and dispatch via `e.target.closest('.feature')`, instead
   of ~6 `addEventListener` calls per row per rebuild. The handlers already use
   `closest` / target tests, so this is a natural refactor. File: `palette.html`
   `appendItems`.

8. **In-place updates instead of full teardown** for state-only refreshes (ties
   to #1/#2): toggle classes and set names on existing rows; keep full rebuild
   only when the feature set actually changes (consider keyed diffing later).
   File: `palette.html`.

9. **Coalesce/debounce `invalidate()`.** `command_terminated_handler` can fire in
   bursts; defer + collapse rapid invalidations into one refresh (Fusion pattern:
   post a custom event + pending flag — note the existing "cannot sendInfoToHTML
   inside the event handler" constraint). Medium complexity; optional. Files:
   `command_terminated_handler`, `invalidate`.

## Recommended order

#4, #5 (safe, immediate API-call reduction) → #3 (selection responsiveness) →
#1, #2, #8 (structure/state + incremental render, the largest win) → #7, #6, #9.

## How to verify the work when it's done

- Add temporary timing around `invalidate()` and the JS render behind the
  existing `debug` flag (`run()`), open a large parametric design, and record
  ms/refresh before vs. after.
- Regression-check the interactions that share the refresh path: roll to a
  feature, rename, add/suppress a feature, collapse/expand groups, and GUI
  selection → row highlight — all must still behave as today.
