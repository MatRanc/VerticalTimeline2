# Performance backlog

The standing TODO is "Improve performance further for very large files." This
file captures a prioritized, execution-ready list of optimizations. It is
documentation only — none of the items below are implemented yet.

Already shipped (v0.5.0): per-feature API-call dedup on the refresh path
(read `obj.entity`/`short_class` once, hoist `app.activeProduct` out of the
loop) and an O(1) GUI-selection highlight via an `entityToken → node id` index.
Those items are removed from the list below.

Also shipped: **#6 below (debounce)** plus a navigation skip-list, fixing the
issue-#9 freeze where a camera pan/orbit gesture fired `commandTerminated`
repeatedly and each one ran a full rebuild. `command_terminated_handler` now
calls `schedule_refresh()` (a 100 ms trailing debounce that marshals back to the
main thread via a custom event) instead of `invalidate()` directly, so a burst
of commands collapses into one refresh.

Also shipped (unreleased): **#2 (roll fast-path)**, **#3 (parent-map cache)**
and **#4 (event delegation)** — see the ✅ notes inline below.

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
3. ~~`get_component_parent_map` walks **all** occurrences every refresh~~ —
   now cached across refreshes (#3 below).
4. The palette JS then does `timeline.innerHTML = ''` and `appendItems`
   (`palette.html`) rebuilds every row from scratch and attaches ~7 event
   listeners per row, every refresh.

Rolling the marker and suppressing/unsuppressing leave the feature *list*
unchanged yet still trigger the full O(N) recompute + full DOM teardown (both
call `invalidate()`) — this is what Tier 1 #1/#2 target. (#2 is now shipped for
palette-initiated rolls; suppress and native-timeline rolls still full-rebuild.
Suppress was deliberately left on the full-rebuild path: suppressing a feature
can change downstream features' health state and an occurrence's parent path,
so an in-place toggle would show stale rows — it needs the #1 state-only
re-read, not a pure client-side toggle.) Renaming already updates the row in
place, and GUI/palette selection uses the O(1) highlight path shipped in
v0.5.0; neither does a full rebuild.

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

2. **Don't full-rebuild on marker-only (roll) changes.** ✅ Shipped for
   palette-initiated rolls (context menu + marker-bar drag): the `rollToFeature`
   handler computes the rolled-back id set from the cached tree — zero Fusion
   API calls, since `rollTo(False)` parks the marker right after the target —
   and returns a `setMarker` command; `applyMarker()` in `palette.html` toggles
   the `suppressed` / `first-rolled-back` classes and `data-rolled-back` attrs
   in place. Any doubt (target not in cache, roll failed) falls back to the
   full rebuild. Not covered: rolls made on Fusion's *native* timeline still
   arrive as `commandTerminated` and full-rebuild — detecting "marker-only"
   there means solving the same structural-ambiguity problem as #1. Also any
   recompute side effect (a re-included feature turning errored) shows on the
   next full refresh, not instantly. Files: `marker_fastpath_command` /
   `rollToFeature` handler (`VerticalTimeline.py`); `applyMarker`
   (`palette.html`).
   **Observed result (2026-07-15, large design):** the in-place update alone
   helped but rolls were still not instant. `~/vt_cmd_trace.log` shows why:
   every marker roll terminates a `FusionRollCommand` (completed), so the
   debounced *full* refresh ran ~100 ms after the in-place update anyway.
   Fixed: the `rollToFeature` handler arms a one-shot 2 s window and
   `command_terminated_handler` consumes exactly one `FusionRollCommand`
   inside it; native-timeline rolls arrive outside the window and refresh
   normally. Needs a retest on a large design — any slowness left after this
   is Fusion's own recompute when the marker moves (kernel work, not fixable
   from the add-in).

## Tier 2 — server-side, low risk

3. **Cache `get_component_parent_map()` across refreshes.** ✅ Shipped.
   `get_cached_component_parent_map()` keys the map on
   `(document name, timeline.count)`, so adds/deletes and document switches
   rebuild it and plain state refreshes reuse it. Accepted staleness: renaming
   or reparenting a component changes neither key, so parent bars can show
   stale ancestry until the next add/delete; key on a rename/move signal if
   users notice. File: `VerticalTimeline.py` (`get_cached_component_parent_map`).

## Tier 3 — palette rendering

4. **Event delegation.** ✅ Shipped. `click` / `dblclick` / `contextmenu` are
   attached once on the `#timeline` container; the handlers already resolved
   the row via `e.target.closest('.feature')`. The 4 name-field listeners stay
   per-row (focus/blur don't bubble). File: `palette.html`.

5. **In-place updates instead of full teardown** for state-only refreshes (ties
   to #1/#2): toggle classes and set names on existing rows; keep full rebuild
   only when the feature set actually changes (consider keyed diffing later).
   File: `palette.html`.

6. **Coalesce/debounce `invalidate()`.** ✅ Shipped (see top). A 100 ms trailing
   `threading.Timer` in `schedule_refresh()` collapses bursts; the timer fires a
   custom event so `invalidate()` runs back on the main thread.

## Remaining slow paths (confirmed 2026-07-15, large design)

User testing after the v0.7.10 work confirmed two paths that still freeze for
seconds on large designs. Documented here because neither has a clean fix from
the add-in today — this is the honest state of things, not an oversight.

- **Rolling the marker on Fusion's *native* timeline** still runs the full
  rebuild, so it feels slower than rolling from the palette (it pays Fusion's
  recompute *plus* the ~6 s rebuild). Half-fixable in principle:
  `FusionRollCommand` identifies the change as marker-only, so the handler
  could read just `markerPosition` and `count` (2 API calls), verify the count
  matches the cache, and reuse the palette-roll fast path. Two things make it
  fragile: mapping a top-level `markerPosition` onto the cached flattened tree
  when collapsed groups are present (members report `index == -1`, and
  adjacent collapsed groups are indistinguishable from leaf indices alone —
  the slot layout has to be reconstructed from the cached tree), and a native
  roll into a collapsed group auto-expands it, changing the slot layout inside
  the same command (the count guard would catch that case and fall back to the
  full rebuild). Doable, but it is the same class of fragility that shelved
  the general incremental refresh — deferred until the shipped wins prove
  stable. Workaround: roll from the palette.

- **Adding a feature (extrude, fillet, …), suppressing, or editing** always
  pays the full rebuild. For adds this is inherent today: the feature set
  genuinely changed, and the API only exposes `Timeline.item(i)`, so the
  add-in must re-read the timeline item by item. The honest fixes are
  Autodesk's bulk accessor (see the README wishlist — out of our hands) or the
  shelved reuse-survivors incremental materialization (#1/#5 above, estimated
  ~6 s → ~0.9 s for an add, with the collapsed-group ambiguity that keeps it
  shelved). Suppress additionally changes downstream health states and
  occurrence parent paths, so it needs the #1 state-only re-read rather than a
  client-side toggle.

## Recommended order

#3 ✅ → #2 ✅ (palette-initiated rolls) → #4 ✅, #6 ✅. Remaining: #1 + #5
(structure/state split + in-place render for everything else — the full
incremental refresh), still shelved on the collapsed-group ambiguity described
in README's wishlist. The *Remaining slow paths* section above maps those open
items to the two slow interactions users actually feel (native rolls, adds).

## How to verify the work when it's done

- Add temporary timing around `invalidate()` and the JS render — gate it on the
  `debug` flag in `run()` (currently declared but unused, so wire it up first),
  open a large parametric design, and record ms/refresh before vs. after.
- Regression-check the interactions that share the refresh path: roll to a
  feature, rename, add/suppress a feature, collapse/expand groups, and GUI
  selection → row highlight — all must still behave as today.
