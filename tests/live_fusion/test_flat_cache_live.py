"""Live stress test for get_flat_timeline/_try_reuse_flat against a real
Fusion timeline (see README.md for how to run this). Builds a scratch model,
drives every structural-change guard, and after each step compares the
cache-reuse path against a fresh full walk (thomasa88lib.timeline.
flatten_timeline) - the same ground truth _try_reuse_flat is trying to
match. Any divergence is a real cache-correctness bug, not a mock artifact.

Findings from the first run of this (2026-07-24): a single-member
TimelineGroup cannot exist in this Fusion version - creation is rejected
by the API ("At least 2 features needed for a group") and shrinking an
existing group down to 1 member auto-dissolves it (confirmed via
parentGroup going from the group to None). So the "stale highlight index on
a collapsed single-member group" gap noted in PERFORMANCE.md appears to be
unreachable, not just narrow/self-healing - re-verify if a future Fusion
version changes this.
"""
import sys
import adsk.core
import adsk.fusion


def run(_context):
    mods = [m for m in sys.modules if m.endswith('VerticalTimeline_py')]
    if not mods:
        print("VerticalTimeline add-in not found in sys.modules - is it running?")
        return
    mod = sys.modules[mods[0]]
    app = adsk.core.Application.get()
    ui = app.userInterface

    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        root = design.rootComponent
        timeline = design.timeline

        log = []

        def check(label):
            cached = mod.get_flat_timeline(timeline)
            truth = mod.timeline.flatten_timeline(timeline)
            cached_objs = [o for o, _ in cached]
            truth_objs = [o for o, _ in truth]
            match = (len(cached_objs) == len(truth_objs) and
                      all(a == b for a, b in zip(cached_objs, truth_objs)))
            log.append(f"{label}: {'PASS' if match else 'FAIL'} "
                       f"n_cached={len(cached_objs)} n_truth={len(truth_objs)} "
                       f"timeline.count={timeline.count}")
            return match

        # --- Build a base model: sketch with 5 rectangles, 5 new-body extrudes. ---
        sketch = root.sketches.add(root.xYConstructionPlane)
        lines = sketch.sketchCurves.sketchLines
        for i in range(5):
            x = i * 3
            lines.addTwoPointRectangle(adsk.core.Point3D.create(x, 0, 0),
                                        adsk.core.Point3D.create(x + 1, 1, 0))
        extrudes = root.features.extrudeFeatures
        exts = []
        for i in range(5):
            prof = sketch.profiles.item(i)
            inp = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(1.0))
            exts.append(extrudes.add(inp))
        check("baseline (sketch + 5 extrudes)")

        # --- Append at the end (new sketch + extrude): the tail-materialize path. ---
        sketch2 = root.sketches.add(root.xYConstructionPlane)
        sketch2.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(20, 0, 0), adsk.core.Point3D.create(21, 1, 0))
        inp = extrudes.createInput(sketch2.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(1.0))
        ext_tail = extrudes.add(inp)
        check("after append at end")

        # --- Mid-history insert: roll marker back, add a feature there. ---
        timeline.markerPosition = 4
        inp = extrudes.createInput(sketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(0.5))
        ext_mid = extrudes.add(inp)
        check("after mid-history insert (marker rolled back before adding)")
        timeline.markerPosition = timeline.count

        # --- Plain delete of a standalone feature. ---
        ext_mid.deleteMe()
        check("after deleting the mid-inserted feature")

        # --- Group creation is rejected below 2 members. ---
        try:
            timeline.timelineGroups.add(0, 0)
            log.append("single-member group creation: UNEXPECTED - Fusion allowed it")
        except RuntimeError:
            log.append("single-member group creation: correctly REJECTED by the API")

        # --- 2-member group: create, collapse, expand. ---
        c = timeline.count
        group = timeline.timelineGroups.add(c - 2, c - 1)
        check("after creating a 2-member group (collapses by default)")
        group.isCollapsed = False
        check("after expanding the group")
        group.isCollapsed = True
        check("after re-collapsing the group")
        group.isCollapsed = False
        check("after expanding again")

        # --- Shrink to 1 member: does the group survive as a single-member group? ---
        member = timeline.item(timeline.count - 1)
        member.entity.deleteMe()
        dissolved = not group.isValid
        log.append(f"group after shrinking to 1 member: {'auto-dissolved' if dissolved else 'still exists'}")
        check("after shrinking the group to 1 member")

        # --- Delete a member INSIDE a collapsed group (count doesn't change -
        # the case the cheap count check alone cannot see). ---
        c = timeline.count
        group2 = timeline.timelineGroups.add(c - 3, c - 1)  # 3 members, collapses immediately
        check("after creating a fresh 3-member group (collapsed by default)")
        # Grab a live handle to an actual current member: expand briefly (the
        # group's span is no longer indexable once collapsed), capture, re-collapse.
        group2.isCollapsed = False
        member_to_delete = timeline.item(c - 3).entity
        group2.isCollapsed = True
        check("after re-collapsing before the hidden delete")
        count_before = timeline.count
        member_to_delete.deleteMe()  # delete a real member directly by handle, group stays collapsed
        count_after = timeline.count
        log.append(f"hidden delete inside collapsed group: count_before={count_before} "
                   f"count_after={count_after} (expected EQUAL)")
        check("after deleting a member INSIDE a collapsed group")
        group2.isCollapsed = False
        check("after expanding to verify the right members remain")

        # --- Real undo/redo through the actual command pipeline. ---
        undo_def = ui.commandDefinitions.itemById('UndoCommand')
        redo_def = ui.commandDefinitions.itemById('RedoCommand')
        undo_def.execute()
        adsk.doEvents()
        check("after real Undo")
        redo_def.execute()
        adsk.doEvents()
        check("after real Redo")

        # --- Force-flag circuit breaker, tested directly. ---
        mod._flat_cache_force = True
        mod.get_flat_timeline(timeline)
        breaker_ok = (mod._flat_cache_force is False)  # only the full-walk branch resets it
        log.append(f"force-flag circuit breaker: {'PASS' if breaker_ok else 'FAIL'}")

        print('\n'.join(log))
        fails = [l for l in log if 'FAIL' in l or 'UNEXPECTED' in l]
        print(f"\n=== {len(log)} lines, {len(fails)} FAILED/UNEXPECTED ===")
    finally:
        doc.close(False)  # never save scratch docs
