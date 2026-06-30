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


if __name__ == '__main__':
    test_burst_coalesces_to_one()
    test_spaced_calls_each_fire()
    print('ok')
