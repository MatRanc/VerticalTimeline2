"""Standalone check for the command-terminated debounce contract.

VerticalTimeline.py can't be imported outside Fusion (it pulls in adsk.*), so
this mirrors schedule_refresh()'s coalescing core (threading.Timer cancel +
reschedule) and asserts the property the real code relies on: a burst of rapid
calls fires exactly once, while calls spaced beyond the window each fire.

Run: python3 test_debounce.py
"""

import threading
import time

DEBOUNCE_SECONDS = 0.05  # short window for a fast test

_timer = None
_lock = threading.Lock()
_fire_count = 0


def _fire():
    global _fire_count
    _fire_count += 1


def schedule_refresh():
    # Mirror of VerticalTimeline.schedule_refresh.
    global _timer
    with _lock:
        if _timer:
            _timer.cancel()
        _timer = threading.Timer(DEBOUNCE_SECONDS, _fire)
        _timer.start()


def test_burst_coalesces_to_one():
    global _fire_count
    _fire_count = 0
    for _ in range(50):                 # a pan-gesture-style burst
        schedule_refresh()
        time.sleep(DEBOUNCE_SECONDS / 10)
    time.sleep(DEBOUNCE_SECONDS * 3)    # let the trailing timer fire
    assert _fire_count == 1, _fire_count


def test_spaced_calls_each_fire():
    global _fire_count
    _fire_count = 0
    for _ in range(3):
        schedule_refresh()
        time.sleep(DEBOUNCE_SECONDS * 3)  # wait past the window each time
    assert _fire_count == 3, _fire_count


# --- navigation skip-list contract ---
# The real #9 fix: command_terminated_handler must NOT schedule a refresh for
# camera/navigation commands (a full timeline rebuild costs ~10s on a large
# design), but must still refresh after real edits. Mirror of the handler's
# decision (kept in sync with VerticalTimeline.SKIP_REFRESH_COMMAND_IDS).

SKIP_REFRESH_COMMAND_IDS = {
    'FreeOrbitCommand', 'OrbitCommand', 'PanCommand', 'ZoomCommand',
    'FitCommand', 'SelectCommand', 'CommitCommand',
}


def schedules_refresh(command_id):
    # Mirror of command_terminated_handler's skip check.
    return command_id not in SKIP_REFRESH_COMMAND_IDS


def test_navigation_does_not_refresh():
    for nav in ['FreeOrbitCommand', 'PanCommand', 'ZoomCommand']:
        assert not schedules_refresh(nav), nav


def test_edits_still_refresh():
    for edit in ['ExtrudeCommand', 'FilletCommand', 'RenameCommand', 'UndoCommand']:
        assert schedules_refresh(edit), edit


if __name__ == '__main__':
    test_burst_coalesces_to_one()
    test_spaced_calls_each_fire()
    test_navigation_does_not_refresh()
    test_edits_still_refresh()
    print('ok')
