"""Standalone check for the lost-projections heuristic (issue #18).

VerticalTimeline.py can't be imported outside Fusion (it pulls in adsk.*), so
this mirrors the health-message substring check in get_features_from_node().
Originally scanned SketchEntity.isLinked/.referencedEntity, on the assumption
that a lost source leaves referencedEntity None - confirmed wrong against a
real lost-projection sketch (2026-07-25): Fusion substitutes a cached, still-
.isValid BRepEdge for the lost source, so neither None-ness nor isValid tells
linked-but-lost apart from linked-and-fine. errorOrWarningMessage's text does;
this is a regression guard against the real message captured from that sketch.
Run: python3 tests/test_lost_projections.py
"""


def sketch_has_lost_projections(health_message):
    # Mirror of the health-message check in VerticalTimeline.get_features_from_node.
    return 'project source is lost' in health_message.lower()


REAL_LOST_PROJECTION_MESSAGE = (
    'Edge 1 missing<b>1 Reference Failures</b><br/>The project source is lost, '
    'Cache is used!Project3Edge 1 missing<b>1 Reference Failures</b><br/>'
    'The project source is lost, Cache is used!Project4Sketch111'
)


def test_real_lost_projection_message_detected():
    assert sketch_has_lost_projections(REAL_LOST_PROJECTION_MESSAGE) is True


def test_empty_message_not_lost():
    assert sketch_has_lost_projections('') is False


def test_unrelated_warning_not_lost():
    assert sketch_has_lost_projections('Edge reference is lost, cache is used!') is False


if __name__ == '__main__':
    test_real_lost_projection_message_detected()
    test_empty_message_not_lost()
    test_unrelated_warning_not_lost()
    print('ok')
