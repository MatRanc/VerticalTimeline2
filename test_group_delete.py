"""Standalone check for the group-contents delete traversal.

VerticalTimeline.py can't be imported outside Fusion (it pulls in adsk.*), so
this mirrors _collect_group_contents() plus the leaf delete ordering and asserts
the properties the real group-delete relies on: every nested leaf is collected,
sub-groups come out deepest-first (so empty shells drop inner-to-outer), and
leaves delete in descending timeline index (so removing one never shifts the
others). Run: python3 test_group_delete.py
"""


class FakeObj:
    def __init__(self, is_group, index=-1):
        self.isGroup = is_group
        self.index = index


class FakeNode:
    def __init__(self, is_group, index=-1, children=None):
        self.obj = FakeObj(is_group, index)
        self.children = children or []


def collect_group_contents(node):
    # Mirror of VerticalTimeline._collect_group_contents.
    leaves, groups = [], []
    def walk(n):
        for child in n.children:
            if child.obj is not None and child.obj.isGroup:
                walk(child)
                groups.append(child)
            else:
                leaves.append(child)
    walk(node)
    return leaves, groups


def test_nested_group():
    A = FakeNode(False, 1)
    C = FakeNode(False, 5)
    sub2 = FakeNode(True, children=[C])
    B = FakeNode(False, 3)
    sub1 = FakeNode(True, children=[B, sub2])
    D = FakeNode(False, 2)
    top = FakeNode(True, children=[A, sub1, D])

    leaves, groups = collect_group_contents(top)

    # every nested leaf collected
    assert {n.obj.index for n in leaves} == {1, 2, 3, 5}, leaves
    # sub-groups deepest-first: sub2 before its parent sub1
    assert groups == [sub2, sub1], groups
    # leaf delete order is descending index
    order = [n.obj.index for n in sorted(leaves, key=lambda n: n.obj.index, reverse=True)]
    assert order == [5, 3, 2, 1], order


def test_empty_group():
    leaves, groups = collect_group_contents(FakeNode(True, children=[]))
    assert leaves == [] and groups == [], (leaves, groups)


if __name__ == '__main__':
    test_nested_group()
    test_empty_group()
    print('ok')
