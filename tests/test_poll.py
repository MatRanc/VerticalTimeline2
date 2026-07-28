"""Standalone check for the timeline-change poll and the roll-command skip.

VerticalTimeline.py can't be imported outside Fusion (it pulls in adsk.*), so
this mirrors _timeline_matches_palette() and the two callers that decide whether
to rebuild: the idle poll (#27 - API/Assistant-created features fire no command
at all) and command_terminated_handler's FusionRollCommand skip (#28 - the
native playback bar's Move to End must refresh, our own palette roll must not).

The property under test: a rebuild happens exactly when the live timeline's
(count, markerPosition) differs from what the palette was last given - never on
a timing window, which is what made #28 intermittent.

Run: python3 test_poll.py
"""

TIMELINE_STATUS_OK = 0
TIMELINE_STATUS_NOT_PARAMETRIC = 2


class Palette:
    """Mirror of the module globals invalidate() maintains."""

    def __init__(self, count, marker):
        self.count = count
        self.marker = marker
        self.rebuilds = 0

    # --- mirror of _timeline_matches_palette ---
    def matches(self, timeline):
        if timeline.status != TIMELINE_STATUS_OK:
            return True
        return timeline.count == self.count and timeline.marker == self.marker

    # --- mirror of invalidate(): rebuild + record what was sent ---
    def invalidate(self, timeline):
        self.rebuilds += 1
        if timeline.status == TIMELINE_STATUS_OK:
            self.count = timeline.count
            self.marker = timeline.marker

    # --- mirror of poll_event_handler ---
    def poll(self, timeline):
        if not self.matches(timeline):
            self.invalidate(timeline)

    # --- mirror of the ROLL_COMMAND_ID branch of command_terminated_handler ---
    def roll_command_terminated(self, timeline):
        if self.matches(timeline):
            return
        self.invalidate(timeline)

    # --- mirror of the rollToFeature fast path: rows updated in place, no
    #     rebuild, but the new marker IS recorded ---
    def fastpath_roll(self, timeline):
        self.count = timeline.count
        self.marker = timeline.marker


class Timeline:
    def __init__(self, count, marker, status=TIMELINE_STATUS_OK):
        self.count = count
        self.marker = marker
        self.status = status


def demo():
    # Nothing changed: polling is free, no rebuild however often it ticks.
    tl = Timeline(10, 10)
    p = Palette(10, 10)
    for _ in range(100):
        p.poll(tl)
    assert p.rebuilds == 0

    # #27: a script/Assistant creates a feature - no command fires, the count
    # grows. The poll must catch it, and exactly once.
    tl = Timeline(11, 11)
    p.poll(tl)
    p.poll(tl)
    assert p.rebuilds == 1, p.rebuilds
    assert (p.count, p.marker) == (11, 11)

    # An API-driven roll (marker only) is caught the same way.
    tl.marker = 4
    p.poll(tl)
    assert p.rebuilds == 2

    # #28: native Move to End. The marker moved, so the FusionRollCommand this
    # fires must rebuild - even immediately after our own palette roll, which is
    # exactly what the old 2 s "eat one roll command" window got wrong.
    p = Palette(11, 11)
    tl = Timeline(11, 4)
    p.fastpath_roll(tl)                 # user rolls back via the palette
    assert p.rebuilds == 0              # fast path, no rebuild
    p.roll_command_terminated(tl)       # the command our own roll fired
    assert p.rebuilds == 0              # still ours: marker is where we put it
    tl.marker = 11                      # native Move to End, 0 s later
    p.roll_command_terminated(tl)
    assert p.rebuilds == 1, 'native roll inside the old 2 s window must refresh'
    assert (p.count, p.marker) == (11, 11)

    # And the poll would have caught it too, had no command fired at all.
    p = Palette(11, 11)
    p.fastpath_roll(Timeline(11, 4))
    p.poll(Timeline(11, 11))
    assert p.rebuilds == 1

    # A timeline we can't read (non-parametric doc / product not ready) counts
    # as matching, so the poll can't spin on it every tick.
    p = Palette(11, 11)
    for _ in range(50):
        p.poll(Timeline(-1, -1, TIMELINE_STATUS_NOT_PARAMETRIC))
    assert p.rebuilds == 0

    print('poll OK')


if __name__ == '__main__':
    demo()
