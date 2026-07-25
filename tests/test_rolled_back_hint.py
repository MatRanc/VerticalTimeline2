"""Standalone check for the issue #24 rolled-back-delete hint.

VerticalTimeline.py can't be imported outside Fusion (it pulls in adsk.*), so
this mirrors the rolled_back/hint branch added to the deleteFeature handler.
Run: python3 test_rolled_back_hint.py
"""

ROLLED_BACK = 4
ERROR = 2


class FakeObj:
    def __init__(self, is_group, health_state):
        self.isGroup = is_group
        self.healthState = health_state


def hint_for(obj):
    # Mirror of the deleteFeature handler's rolled_back/hint logic.
    rolled_back = not obj.isGroup and obj.healthState == ROLLED_BACK
    return ('\n\nRolled-back features have nothing computed to select - '
            'delete from the native timeline instead.') if rolled_back else ''


def test_rolled_back_feature_gets_hint():
    assert hint_for(FakeObj(False, ROLLED_BACK)) != ''


def test_healthy_or_error_feature_gets_no_hint():
    assert hint_for(FakeObj(False, ERROR)) == ''


def test_group_never_gets_hint():
    # A group's own healthState isn't meaningful here; the check must exclude
    # groups even if healthState happens to read ROLLED_BACK.
    assert hint_for(FakeObj(True, ROLLED_BACK)) == ''


if __name__ == '__main__':
    test_rolled_back_feature_gets_hint()
    test_healthy_or_error_feature_gets_no_hint()
    test_group_never_gets_hint()
    print('ok')
