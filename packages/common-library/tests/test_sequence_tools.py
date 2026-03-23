import itertools
from collections import Counter

import pytest
from common_library.sequence_tools import interleave_by_key


@pytest.mark.parametrize(
    "items, key",
    [
        pytest.param([], lambda x: x, id="empty"),
        pytest.param(["a"], lambda x: x, id="single"),
    ],
)
def test_interleave_noop_for_trivial_inputs(items: list[str], key):
    assert interleave_by_key(items, key=key) == items


def test_interleave_spreads_groups():
    items = ["a1", "a2", "a3", "b1", "b2", "c1"]
    result = interleave_by_key(items, key=lambda x: x[0])

    assert Counter(result) == Counter(items)

    # No two consecutive items share the same key
    keys = [x[0] for x in result]
    consecutive_same = sum(1 for a, b in itertools.pairwise(keys) if a == b)
    assert consecutive_same == 0, f"Got consecutive duplicates: {keys}"


def test_interleave_preserves_all_items():
    items = ["a1", "a2", "b1", "b2", "c1", "c2"]
    result = interleave_by_key(items, key=lambda x: x[0])
    assert Counter(result) == Counter(items)


def test_interleave_all_same_key():
    items = [f"a{i}" for i in range(5)]
    result = interleave_by_key(items, key=lambda _: "same")
    assert Counter(result) == Counter(items)
    assert len(result) == 5


def test_interleave_many_keys_one_each():
    items = [f"item_{i}" for i in range(10)]
    result = interleave_by_key(items, key=lambda x: x)
    assert Counter(result) == Counter(items)
    # All keys are unique so no consecutive duplicates possible
    consecutive_same = sum(1 for a, b in itertools.pairwise(result) if a == b)
    assert consecutive_same == 0
