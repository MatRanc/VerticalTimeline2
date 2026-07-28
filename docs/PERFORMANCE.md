# Performance backlog

The standing TODO is "Improve performance further for very large files." Most
of the backlog below is shipped — see [CHANGELOG.md](../CHANGELOG.md) for
what and when, and the function docstrings named inline below for how. This
file keeps what those two don't: the underlying cost model (measured, not
guessed), the correctness case for the caches, and what's still open.

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

## Tier 1 — biggest wins

1. **Skip per-feature work that didn't change (structure vs. state).** ✅
   Shipped. `get_flat_timeline()` / `_try_reuse_flat()` (`VerticalTimeline.py`)
   — mechanism and edge cases are in the function docstrings; mirror test
   `test_flat_cache.py`. Measured result: CHANGELOG.md v0.7.10.

2. **Don't full-rebuild on marker-only (roll) changes.** ✅ Shipped for
   palette-initiated rolls (context menu + marker-bar drag).
   `marker_fastpath_command()` / `rollToFeature` handler
   (`VerticalTimeline.py`); `applyMarker()` (`palette.html`) — mechanism and
   the self-fired-`FusionRollCommand` skip (a marker comparison, not a time
   window — see #28) are documented at the call sites. The old ceiling
   (recompute side effects invisible until the next full refresh) is gone: the
   payload now carries each row's health — 29 µs/node, **12.6 ms for a 436-node
   cache** (measured 2026-07-27), versus 250 ms for a warm full rebuild (#29). Not covered: rolls made on Fusion's *native* timeline
   still full-rebuild — detecting "marker-only" there means solving the same
   structural-ambiguity problem as #1.

## Tier 2 — server-side, low risk

3. **Cache `get_component_parent_map()` across refreshes.** ✅ Shipped.
   `get_cached_component_parent_map()` (`VerticalTimeline.py`) — keying and
   the accepted rename/reparent staleness tradeoff are documented at the
   call site.

## Tier 3 — palette rendering

4. **Event delegation.** ✅ Shipped. `click` / `dblclick` / `contextmenu`
   delegated from the `#timeline` container in `palette.html` (see the
   comment above the listeners there).

5. **In-place updates instead of full teardown** for state-only refreshes (ties
   to #1/#2): toggle classes and set names on existing rows; keep full rebuild
   only when the feature set actually changes (consider keyed diffing later).
   File: `palette.html`. **Open.**

6. **Coalesce/debounce `invalidate()`.** ✅ Shipped. `schedule_refresh()`
   (`VerticalTimeline.py`) — fixed the issue #9 pan/orbit freeze; mechanism
   documented at the call site.

7. **Idle poll for change signals no event reports** (#27). ✅ Shipped.
   `poll_event_handler()` / `_timeline_matches_palette()`
   (`VerticalTimeline.py`). A tick compares `timeline.count` /
   `timeline.markerPosition` against what the palette was last given and only
   calls `invalidate()` when one of them moved. Measured **~0.6 ms per tick**
   (2026-07-27, 361-node design) — the property reads are free, the
   `get_timeline()` product lookup is the cost — so the 0.5 s interval spends
   ~0.1% of one core on an idle design. Mirror test `test_poll.py`.

## Remaining slow paths

What still runs the full ~6 s `item(i)` walk, beyond the guard table above:

- **Deletes** — a held wrapper goes invalid, so the cache correctly refuses to
  reuse itself. A repair pass is possible (drop the invalid wrappers when the
  count delta matches and fix up the stored indices) but deletes recompute the
  model anyway and are rarer than rolls/adds; add it if users notice. **Open.**
- **Middle inserts** (rolling back and extruding mid-history) — the append
  heuristic requires the marker at the end; a middle insert is detectable but
  placing the new object into the flattened order safely needs more than a
  tail check. Fallback is always correct, just slow. **Open.**
- **First refresh after a document switch** — cold cache, inherent.
- **Fusion's own recompute** when the marker moves or a feature lands — kernel
  work, invisible to and unfixable by any add-in.

## Autodesk API wishlist

**A bulk timeline accessor** ([#26](https://github.com/MatRanc/VerticalTimeline2/issues/26)).
`Timeline` exposes only `.count` and
`.item(index)`, and each `.item()` call costs ~6 ms regardless of index
(measured live, 2026-07-15) — ~6 s to read a ~1450-object timeline. A single
call returning the whole timeline as an array — a `Timeline.asArray()` /
`allItems`, like many other Fusion collections already provide — would turn
that into one round-trip and remove every remaining full-walk case above
(deletes, middle inserts, reorders, cold cache after a document switch). A
"timeline changed" event carrying the delta would be even better. *If you
work on the Fusion API team: please add this.*

## Recommended order

Everything else is shipped (✅ above). Remaining, in value order: the
delete-repair pass, the middle-insert repair, then #5 (in-place DOM updates —
the payload side is now fast, so this is purely about skipping the JS
teardown).

## How to verify the work when it's done

- Add temporary timing around `invalidate()` and the JS render — gate it on the
  `debug` flag in `run()` (currently declared but unused, so wire it up first),
  open a large parametric design, and record ms/refresh before vs. after.
- Regression-check the interactions that share the refresh path: roll to a
  feature, rename, add/suppress a feature, collapse/expand groups, and GUI
  selection → row highlight — all must still behave as today.
