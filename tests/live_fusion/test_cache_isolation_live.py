"""Live test that _flat_cache_timeline identity keying actually isolates
state between documents (see README.md for how to run this). Builds two
different scratch models, switches the active document back and forth, and
confirms the cache always rebuilds correctly for whichever one is active
rather than serving stale data left over from the other.
"""
import sys
import adsk.core
import adsk.fusion


def _build_model(root, n):
    sketch = root.sketches.add(root.xYConstructionPlane)
    lines = sketch.sketchCurves.sketchLines
    for i in range(n):
        x = i * 3
        lines.addTwoPointRectangle(adsk.core.Point3D.create(x, 0, 0),
                                    adsk.core.Point3D.create(x + 1, 1, 0))
    extrudes = root.features.extrudeFeatures
    for i in range(n):
        inp = extrudes.createInput(sketch.profiles.item(i), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(1.0))
        extrudes.add(inp)


def run(_context):
    mods = [m for m in sys.modules if m.endswith('VerticalTimeline_py')]
    if not mods:
        print("VerticalTimeline add-in not found in sys.modules - is it running?")
        return
    mod = sys.modules[mods[0]]
    app = adsk.core.Application.get()
    original_active = app.activeDocument

    doc_a = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design_a = adsk.fusion.Design.cast(app.activeProduct)
    _build_model(design_a.rootComponent, 3)  # doc A: 4 items (sketch + 3 extrudes)
    timeline_a = design_a.timeline

    doc_b = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design_b = adsk.fusion.Design.cast(app.activeProduct)
    _build_model(design_b.rootComponent, 5)  # doc B: 6 items (sketch + 5 extrudes)
    timeline_b = design_b.timeline

    try:
        def check(label, timeline, expected_leaf_count):
            cached = mod.get_flat_timeline(timeline)
            truth = mod.timeline.flatten_timeline(timeline)
            cached_objs = [o for o, _ in cached]
            truth_objs = [o for o, _ in truth]
            match = (len(cached_objs) == len(truth_objs) == expected_leaf_count and
                      all(a == b for a, b in zip(cached_objs, truth_objs)))
            key_ok = mod._flat_cache_timeline == timeline
            print(f"{label}: {'PASS' if match and key_ok else 'FAIL'} "
                  f"n_cached={len(cached_objs)} n_truth={len(truth_objs)} "
                  f"expected={expected_leaf_count} cache_keyed_to_this_timeline={key_ok}")
            return match and key_ok

        results = []
        doc_a.activate()
        results.append(check("doc A active", timeline_a, 4))
        doc_b.activate()
        results.append(check("doc B active (switch from A)", timeline_b, 6))
        doc_a.activate()
        results.append(check("doc A active again (switch back from B)", timeline_a, 4))
        doc_b.activate()
        results.append(check("doc B active again", timeline_b, 6))

        print(f"\n=== {len(results)} checks, {results.count(False)} FAILED ===")
    finally:
        doc_a.close(False)
        doc_b.close(False)
        try:
            original_active.activate()
        except Exception:
            pass
