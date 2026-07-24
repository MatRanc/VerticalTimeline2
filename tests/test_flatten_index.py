"""Standalone check for flatten_timeline's (obj, native_index) pairs.

thomasa88lib.timeline can't be imported outside Fusion (it pulls in adsk.*), so
this mirrors flatten_timeline and asserts the index bookkeeping the selection
highlight relies on (#14): top-level items carry their collection position —
which is what TimelineObject.index reports for them, with a collapsed group
occupying one slot — and items inside collapsed groups carry -1 (matching what
.index reports there). Run: python3 test_flatten_index.py
"""


class FakeItem:
    def __init__(self, name, children=None):
        self.name = name
        self.isGroup = children is not None
        self._children = children or []
        self.count = len(self._children)

    def item(self, i):
        return self._children[i]


def flatten_timeline(timeline_collection, _in_group=False):
    # Mirror of thomasa88lib.timeline.flatten_timeline.
    flat_collection = []
    for i in range(timeline_collection.count):
        obj = timeline_collection.item(i)
        if obj.isGroup:
            flat_collection += flatten_timeline(obj, _in_group=True)
        else:
            flat_collection.append((obj, -1 if _in_group else i))
    return flat_collection


def demo():
    # A collapsed group occupies one top-level slot: the item after it must get
    # index 3, not 2 — using the flat position instead would highlight the
    # wrong row for every feature after a collapsed group.
    a, b, d, e, f = (FakeItem(n) for n in 'abdef')
    group = FakeItem('g', children=[d, e])
    flat = flatten_timeline(FakeItem('root', children=[a, b, group, f]))
    assert [(o.name, i) for o, i in flat] == [
        ('a', 0), ('b', 1), ('d', -1), ('e', -1), ('f', 3)], flat

    # Nested collapsed groups: everything inside is -1, top level unaffected.
    inner = FakeItem('inner', children=[FakeItem('x')])
    outer = FakeItem('outer', children=[FakeItem('c'), inner])
    flat = flatten_timeline(FakeItem('root', children=[outer, FakeItem('z')]))
    assert [(o.name, i) for o, i in flat] == [
        ('c', -1), ('x', -1), ('z', 1)], flat

    print('flatten index OK')


if __name__ == '__main__':
    demo()
