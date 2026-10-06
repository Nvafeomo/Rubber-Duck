import ast

from rubberduck.mutations import dict_key_swap, loop_iterable_swap, variable_swap

FIXTURE = '''\
def build_record(items, other):
    """Save a record under its name and total the items."""
    row = {"name": items[0], "id": other}
    total = 0
    for value in items:
        total += value
    return row["name"], total
'''


def _only_change(mutation, source):
    assert mutation is not None
    ast.parse(mutation.source)
    original = source.splitlines()
    updated = mutation.source.splitlines()
    assert len(original) == len(updated)
    changed = [number for number, (left, right) in enumerate(zip(original, updated), start=1) if left != right]
    assert changed == [mutation.line]
    return mutation


def test_variable_swap_replaces_one_use():
    mutation = _only_change(variable_swap(FIXTURE), FIXTURE)
    assert mutation.operator == "variable_swap"
    assert mutation.line == 3
    assert "other[0]" in mutation.source.splitlines()[2]
    assert "items[0]" not in mutation.source.splitlines()[2]


def test_dict_key_swap_replaces_one_key():
    mutation = _only_change(dict_key_swap(FIXTURE), FIXTURE)
    assert mutation.operator == "dict_key_swap"
    assert mutation.line == 3
    assert "'id': items[0]" in mutation.source or '"id": items[0]' in mutation.source


def test_loop_iterable_swap_points_at_the_other_name():
    mutation = _only_change(loop_iterable_swap(FIXTURE), FIXTURE)
    assert mutation.operator == "loop_iterable_swap"
    assert mutation.line == 5
    assert "for value in other:" in mutation.source


def test_operators_decline_when_the_function_has_no_pair():
    assert variable_swap("def only(name):\n    return name\n") is None
    assert dict_key_swap("def no_key(items, other):\n    return items + other\n") is None
    assert loop_iterable_swap("def no_loop(items):\n    for value in items:\n        return value\n") is None
