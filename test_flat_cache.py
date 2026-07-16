"""Standalone check for the flat-timeline cache reuse rules.

VerticalTimeline.py can't be imported outside Fusion (it pulls in adsk.*), so
this mirrors _try_reuse_flat and asserts the guards measured/verified live on
2026-07-15: same count + all wrappers valid -> reuse; any invalid wrapper
(delete), a shrunk count, a middle insert (marker below count), a new group,
or a collapsed-group tail -> full walk (None). A marker-at-end append reuses
the old wrappers and materializes only the tail. Run: python3 test_flat_cache.py
"""


class FakeObj:
    def __init__(self, name, valid=True, group=False):
        self.name = name
        self.isValid = valid
        self.isGroup = group


class FakeTimeline:
    def __init__(self, objs, marker=None):
        self._objs = objs
        self.count = len(objs)
        self.markerPosition = self.count if marker is None else marker

    def item(self, i):
        return self._objs[i]


def try_reuse_flat(timeline, count, cache, cache_count):
    # Mirror of VerticalTimeline._try_reuse_flat (module globals passed in).
    if count < cache_count:
        return None
    if any(not obj.isValid for obj, _ in cache):
        return None
    if count == cache_count:
        return cache
    if timeline.markerPosition != count:
        return None
    new_objs = [timeline.item(i) for i in range(cache_count, count)]
    if any(obj.isGroup for obj in new_objs):
        return None
    if cache_count > 0:
        if not cache or timeline.item(cache_count - 1) != cache[-1][0]:
            return None
    return cache + list(zip(new_objs, range(cache_count, count)))


def demo():
    a, b, c = FakeObj('a'), FakeObj('b'), FakeObj('c')
    cache = [(a, 0), (b, 1), (c, 2)]
    tl = FakeTimeline([a, b, c])

    # Unchanged: reuse as-is.
    assert try_reuse_flat(tl, 3, cache, 3) is cache

    # A held wrapper went invalid (deleted, possibly inside a collapsed
    # group where the count doesn't change): full walk.
    b.isValid = False
    assert try_reuse_flat(tl, 3, cache, 3) is None
    b.isValid = True

    # Count shrank: full walk.
    assert try_reuse_flat(FakeTimeline([a, b]), 2, cache, 3) is None

    # Append with marker at the end: reuse + materialize only the tail.
    d = FakeObj('d')
    grown = FakeTimeline([a, b, c, d])
    out = try_reuse_flat(grown, 4, cache, 3)
    assert out == [(a, 0), (b, 1), (c, 2), (d, 3)], out

    # Middle insert leaves the marker below count: full walk.
    grown_mid = FakeTimeline([a, b, d, c], marker=3)
    assert try_reuse_flat(grown_mid, 4, cache, 3) is None

    # The new tail object is a group (group create/collapse): full walk.
    g = FakeObj('g', group=True)
    assert try_reuse_flat(FakeTimeline([a, b, c, g]), 4, cache, 3) is None

    # Tail slot identity changed (e.g. the old tail is now inside a collapsed
    # group, so item() returns the group object, not the cached leaf): full walk.
    swapped = FakeTimeline([a, b, g, d])
    assert try_reuse_flat(swapped, 4, cache, 3) is None

    # Growth from an empty timeline appends without a tail check.
    out = try_reuse_flat(FakeTimeline([a, b]), 2, [], 0)
    assert out == [(a, 0), (b, 1)], out

    print('flat cache OK')


if __name__ == '__main__':
    demo()
