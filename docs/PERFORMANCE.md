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

Also shipped (unreleased): **#1 (wrapper-reuse flat cache — the big one:
6.36 s → 0.25 s measured)**, **#2 (roll fast-path)**, **#3 (parent-map
cache)** and **#4 (event delegation)** — see the ✅ notes inline below. The
2026-07-15 items were profiled and verified live in a running Fusion via MCP
script execution.

## Considered and rejected: rewrite in C++

Fusion add-ins can be written in C++, but that won't speed this one up. Every slow
operation is an API call into Fusion's own compiled kernel (`obj.entity`, icon
resolution, timeline traversal) plus the HTML palette round-trip. A C++ add-in
calls the same API and waits on the same kernel and palette — it only saves Python
*dispatch* overhead (microseconds, against millisecond-plus API calls). Cost:
full ~1600-line rewrite, drop `thomasa88lib` (Python-only), per-platform compiles
(Windows + mac), and loss of Shift+S hot reload / `editEnabled` iteration. The real
lever is the Tier 1–3 items below.

## Where the time goes — MEASURED (2026-07-15, live 1054-slot / 1437-leaf design)

Profiled in the running Fusion via MCP script execution. The old assumptions
in this file were wrong; the measured breakdown of the ~6.4 s refresh:

| phase | time |
|---|---|
| `flatten_timeline` — the `Timeline.item(i)` walk | **6.10 s (95%)** |
| `get_features_from_node` — entity reads, icons, parent paths | 0.29 s |
| `get_component_parent_map` (264 components) | 0.018 s |
| `build_timeline_tree` | 0.009 s |
| state re-read (name/isSuppressed/isRolledBack/health ×1404 held wrappers) | 0.019 s |

Key API facts (all measured live):
- `Timeline.item(i)` costs ~6 ms **flat, regardless of index** — materializing
  a wrapper is what's expensive, so the walk is O(N)×6 ms.
- Property reads on **already-held** wrappers are *microseconds*, and held
  wrappers are **live views**: external suppress/roll/rename/health changes
  read back correctly through them (verified both directions).
- A deleted object's held wrapper flips `isValid` (a full-cache sweep is
  ~3 ms); other wrappers are unaffected.
- `TimelineObject.index` is NOT cheap (~3 ms — internal position lookup) and
  RAISES (`InternalValidationError`) for members of collapsed groups rather
  than returning -1.
- Wrapper equality (`==`) is native-object identity, ~0.014 ms.

So the entire game is: **never re-run the `item(i)` walk unless the structure
actually changed**. Everything downstream is already fast.

## Can the cache show an outdated timeline?

Row **state can never go stale**: the cache stores object *references*, not
copied values. Every refresh re-reads name / `isSuppressed` / `isRolledBack` /
health / entity / icons / parent paths through the held wrappers, and those
are live views into Fusion (verified both directions). Rename something,
suppress it, roll past it — the next refresh shows it correctly whether or not
the cache was reused.

What the cache pins is the **set and order** of rows. Each way those can
change, and its guard:

| change | guard |
|---|---|
| add (anywhere) | `timeline.count` grew → append path or full walk |
| delete (incl. inside a collapsed group, where count doesn't change) | `isValid` sweep over every held wrapper |
| group collapse/expand, group create/delete | count changes (collapsed groups occupy one slot); expanded groups don't affect the flat list, and the tree/grouping is rebuilt from live `parentGroup` reads every refresh |
| reorder, undo, redo | `FORCE_FULL_REFRESH_COMMAND_IDS` (all undo/redo entry points + `FusionReorderCommand`) force the full walk |
| document switch / reopen | cache is keyed on the Timeline object's identity |
| anything that throws during validation | falls back to the full walk |

Residual gaps, both self-healing at the next add/delete/undo/switch:

1. **An order-changing command outside the force list.** The main path
   (dragging a feature in the native timeline, `FusionReorderCommand`) is
   verified against a real drag with `TRACE_COMMANDS` (2026-07-24): it fires
   with `terminationReason=Completed` and is correctly force-invalidated.
   What's left is genuinely unknown-unknowns territory - some *other*,
   undiscovered command that also reorders the timeline while keeping count
   unchanged and every wrapper valid, that isn't on the list. If one exists,
   it would show rows in a stale *order* — never stale *state*, never
   missing/extra rows — until the next structural refresh (any add, delete,
   undo, or doc switch, which happen constantly in normal use). If it ever
   shows up, capture the id with `TRACE_COMMANDS` and extend the set.
2. **Collapsing/expanding a single-member group** - turns out this can't
   actually happen in current Fusion (verified 2026-07-24, live): creating a
   group with fewer than 2 members is rejected by the API
   (`timelineGroups.add()` raises "At least 2 features needed for a group"),
   and shrinking an existing group down to 1 member auto-dissolves it back to
   a plain ungrouped row (confirmed via `parentGroup` flipping to `None`). So
   this gap is unreachable, not just self-healing - re-verify if a future
   Fusion version changes either behavior.

The middle-insert case is excluded by construction: new features always land
at the marker, so an insert that isn't at the very end leaves
`markerPosition < count` and the append path refuses it (full walk).

With the #1 wrapper-reuse cache shipped, any refresh that keeps the feature
set intact — suppress/unsuppress, renames, rolls from either timeline, sketch
edits, health changes — reuses the held wrappers and costs ~0.25 s instead of
~6.4 s; the state is re-read through the wrappers so nothing goes stale
(suppress-changed downstream health and occurrence parent paths included,
since the payload pass re-reads those every refresh anyway).

## Tier 1 — biggest wins

1. **Skip per-feature work that didn't change (structure vs. state).**
   ✅ Shipped, in a simpler form than sketched here: the measured numbers show
   the per-feature payload rebuild is cheap (0.29 s) and only the `item(i)`
   walk is expensive, so instead of splitting the payload, `get_flat_timeline`
   caches the **flattened wrapper list** across refreshes and reuses it when a
   cheap validation passes: same `timeline.count` + every held wrapper
   `isValid` (~10 ms total) + no order-changing command seen
   (`FORCE_FULL_REFRESH_COMMAND_IDS`: undo/redo/reorder). A count that grew
   with the marker at the end and an unchanged tail wrapper is treated as an
   append (the plain extrude) — only the new tail objects are materialized.
   Anything doubtful falls back to the full walk. Measured on the live
   1054-slot design: refresh 6.36 s → **0.25 s**; the append path adds ~1 ms.
   Verified end-to-end: suppress / native roll / append reflect correct state
   through the reuse path, deletes fall back, and the reused cache is
   object-identical to a fresh walk. Files: `get_flat_timeline` /
   `_try_reuse_flat` (`VerticalTimeline.py`), mirror test `test_flat_cache.py`.

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

## Remaining slow paths (updated after the 2026-07-15 MCP-verified work)

The two big complaints from earlier that day — native-timeline rolls and adds
at the end — were **fixed the same evening** by the wrapper-reuse cache (#1
above), once live profiling showed the real cost model. Native rolls needed no
marker-slot math at all: the count is unchanged, so the reuse path simply
re-reads `isRolledBack` through the held wrappers (microseconds each). What
still runs the full ~6 s `item(i)` walk:

- **Deletes** — a held wrapper goes invalid, so the cache correctly refuses to
  reuse itself. A repair pass is possible (drop the invalid wrappers when the
  count delta matches and fix up the stored indices) but deletes recompute the
  model anyway and are rarer than rolls/adds; add it if users notice.
- **Middle inserts** (rolling back and extruding mid-history) — the append
  heuristic requires the marker at the end; a middle insert is detectable but
  placing the new object into the flattened order safely needs more than a
  tail check. Fallback is always correct, just slow.
- **Reorders, undo, redo** (`FORCE_FULL_REFRESH_COMMAND_IDS`) — these can
  change order while keeping every wrapper valid and the count unchanged, so
  only the command id reveals them; they force the full walk by design.
- **First refresh after a document switch** — cold cache, inherent.
- **Fusion's own recompute** when the marker moves or a feature lands — kernel
  work, invisible to and unfixable by any add-in.

The bulk accessor ask to Autodesk (README wishlist) still stands: it would
remove the cold-cache walk too.

## Recommended order

#1 ✅, #2 ✅, #3 ✅, #4 ✅, #6 ✅. Remaining, in value order: a delete-repair
pass for the flat cache, a middle-insert repair, and #5 (in-place DOM updates —
the payload side is now fast, so this is purely about skipping the JS
teardown). See *Remaining slow paths* above.

## How to verify the work when it's done

- Add temporary timing around `invalidate()` and the JS render — gate it on the
  `debug` flag in `run()` (currently declared but unused, so wire it up first),
  open a large parametric design, and record ms/refresh before vs. after.
- Regression-check the interactions that share the refresh path: roll to a
  feature, rename, add/suppress a feature, collapse/expand groups, and GUI
  selection → row highlight — all must still behave as today.
