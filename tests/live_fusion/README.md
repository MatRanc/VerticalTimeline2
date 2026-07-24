# Live Fusion tests

Unlike the mock-based `test_*.py` at the repo root (which mirror the caching
logic with fake objects and run under plain `python3`), these exercise the
real `VerticalTimeline` cache functions against a real, running Fusion
session and a real timeline - no mocks. Each script always works in a
scratch document (`app.documents.add(...)`, closed with `doc.close(False)`)
and never touches or saves any document you have open.

## Requirements

- Fusion running with the VerticalTimeline add-in loaded (these look it up
  via `sys.modules` and call its internals directly, e.g. `get_flat_timeline`,
  `marker_fastpath_command`, `timeline_cache_tree`).
- A way to execute a Python script inside Fusion's process. Either:
  - Fusion's **Scripts and Add-Ins** panel: add the file as a script, Run.
  - The VerticalTimeline MCP dev bridge (`fusion_mcp_execute`, featureType
    `"script"`, `object.script` = the file's contents) - see
    `../../fusion-mcp-access` project memory if you're driving this from
    Claude Code.

Each file defines a single `run(_context)` entry point, matching Fusion's
script contract directly, so it works unmodified either way.

## Files

- `test_flat_cache_live.py` - every structural-change guard in
  `get_flat_timeline`/`_try_reuse_flat`: append, mid-history insert, plain
  delete, delete of a member *inside a collapsed group* (count doesn't
  change - the one case the cheap count check alone can't see), group
  create/collapse/expand, the single-member-group edge case (and whether
  it's even reachable), real undo/redo through the actual command pipeline,
  and the `_flat_cache_force` circuit breaker itself.
- `test_roll_fastpath_live.py` - `marker_fastpath_command` against a real
  `rollTo()`, cross-checked leaf-by-leaf against Fusion's own live
  `isRolledBack`, not a mock.
- `test_cache_isolation_live.py` - the cache doesn't leak state between two
  different documents when the active document switches.

Each script prints a PASS/FAIL line per check and a final tally; a non-empty
list of failures is printed explicitly rather than just a silent exit code,
since these are meant to be read from the tool output, not a CI runner.

## Known gap these can't cover

There is no public Fusion API to reorder timeline features
programmatically - only the interactive drag command (`FusionReorderCommand`).
These scripts can't simulate that gesture, so they can't independently
confirm every real reorder path fires an id already in
`FORCE_FULL_REFRESH_COMMAND_IDS`. To check that by hand: flip
`TRACE_COMMANDS = True` in `VerticalTimeline.py` (or set it live on the
running module), drag one feature to a new position in the timeline, and
read `~/vt_cmd_trace.log`.
