"""Standalone check for the roll fast-path's rolled-back-set computation.

VerticalTimeline.py can't be imported outside Fusion (it pulls in adsk.*), so
this mirrors marker_fastpath_command's tree walk and asserts the invariants the
in-place marker update (PERFORMANCE.md Tier 1 #2) relies on: rollTo(False)
keeps the target computed, everything after it in display order is rolled
back, and a group header is rolled back only when all of its leaves are.
Run: python3 test_roll_fastpath.py
"""


class FakeNode:
    _next_id = 0

    def __init__(self, name, children=None):
        self.name = name
        self.id = FakeNode._next_id
        FakeNode._next_id = self.id + 1
        self.obj = object()
        self.children = children or []


def rolled_ids(tree, target):
    # Mirror of the walk in VerticalTimeline.marker_fastpath_command.
    while target.children:
        target = target.children[-1]

    rolled = []
    seen_target = [False]
    def walk(node):
        all_rolled = bool(node.children)
        for child in node.children:
            if child.children:
                child_rolled = walk(child)
                if child_rolled:
                    rolled.append(child.id)
                all_rolled = all_rolled and child_rolled
            else:
                if seen_target[0]:
                    rolled.append(child.id)
                else:
                    all_rolled = False
                if child is target:
                    seen_target[0] = True
        return all_rolled
    walk(tree)
    assert seen_target[0], 'target must be found in the tree'
    return {n for n in rolled}


def names(tree, ids):
    out = set()
    def walk(node):
        for child in node.children:
            if child.id in ids:
                out.add(child.name)
            walk(child)
    walk(tree)
    return out


def demo():
    # Flat timeline: rolling to b keeps a and b, rolls back c and d.
    a, b, c, d = (FakeNode(n) for n in 'abcd')
    tree = FakeNode('root', [a, b, c, d])
    assert names(tree, rolled_ids(tree, b)) == {'c', 'd'}

    # Rolling to the last item rolls back nothing.
    assert names(tree, rolled_ids(tree, d)) == set()

    # Marker inside a group: the group header is NOT rolled back (only some of
    # its leaves are), rows after the target are.
    d, e = FakeNode('d'), FakeNode('e')
    a, f = FakeNode('a'), FakeNode('f')
    g = FakeNode('g', [d, e])
    tree = FakeNode('root', [a, g, f])
    assert names(tree, rolled_ids(tree, d)) == {'e', 'f'}

    # Marker before a group: all its leaves are rolled back, so the header is too.
    assert names(tree, rolled_ids(tree, a)) == {'g', 'd', 'e', 'f'}

    # Rolling onto the group targets its last leaf: nothing in the group rolls.
    assert names(tree, rolled_ids(tree, g)) == {'f'}

    # Nested groups roll as a unit when fully past the marker.
    x = FakeNode('x')
    inner = FakeNode('inner', [x])
    cc = FakeNode('c')
    outer = FakeNode('outer', [cc, inner])
    z = FakeNode('z')
    a = FakeNode('a')
    tree = FakeNode('root', [a, outer, z])
    assert names(tree, rolled_ids(tree, a)) == {'outer', 'inner', 'c', 'x', 'z'}

    print('roll fastpath OK')


if __name__ == '__main__':
    demo()
