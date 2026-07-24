"""Live stress test for marker_fastpath_command (see README.md for how to
run this). The mock version at test_roll_fastpath.py mirrors the tree-walk
logic with FakeNode; this drives a real rollTo() on a real timeline and
cross-checks the fastpath's claimed rolled-set against Fusion's own live
isRolledBack on every leaf - ground truth, not a re-implementation.
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

    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        root = design.rootComponent
        timeline = design.timeline

        sketch = root.sketches.add(root.xYConstructionPlane)
        lines = sketch.sketchCurves.sketchLines
        for i in range(5):
            x = i * 3
            lines.addTwoPointRectangle(adsk.core.Point3D.create(x, 0, 0),
                                        adsk.core.Point3D.create(x + 1, 1, 0))
        extrudes = root.features.extrudeFeatures
        for i in range(5):
            prof = sketch.profiles.item(i)
            inp = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(1.0))
            extrudes.add(inp)
        # Group the middle three extrudes so the walk covers a group header too.
        timeline.timelineGroups.add(2, 4)

        def leaf_mismatches(fastpath):
            fast_rolled_ids = set(fastpath['data']['rolled']) if fastpath else set()
            mismatches = []

            def walk(node):
                if node.children:
                    for c in node.children:
                        walk(c)
                else:
                    if node.obj is None:
                        return
                    actual = node.obj.isRolledBack
                    claimed = node.id in fast_rolled_ids
                    if actual != claimed:
                        mismatches.append((node.id, getattr(node.obj, 'name', '?'), actual, claimed))
            walk(mod.timeline_cache_tree)
            return mismatches

        results = []
        # Roll to a few different targets to cover different positions
        # relative to the group.
        mod.invalidate(send=False)
        node_ids = list(mod.timeline_cache_map.keys())
        targets = [node_ids[1], node_ids[len(node_ids) // 2], node_ids[-1]]

        for target_id in targets:
            mod.invalidate(send=False)  # fresh cache before each roll
            target_node = mod.timeline_cache_map[target_id]
            obj = target_node.obj
            name = getattr(obj, 'name', '?')
            rolled_ok = obj.rollTo(False)
            fastpath = mod.marker_fastpath_command(target_node) if rolled_ok else None
            mismatches = leaf_mismatches(fastpath) if fastpath else ['fastpath returned None']
            ok = not mismatches
            results.append(f"roll to {name!r} (id={target_id}): {'PASS' if ok else 'FAIL'} "
                           f"rollTo_ok={rolled_ok} mismatches={mismatches}")

        print('\n'.join(results))
        fails = [r for r in results if 'FAIL' in r]
        print(f"\n=== {len(results)} roll targets, {len(fails)} FAILED ===")
    finally:
        doc.close(False)  # never save scratch docs
