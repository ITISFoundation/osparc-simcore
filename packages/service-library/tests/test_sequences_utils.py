from typing import Any, Iterable

import pytest
from servicelib.sequences_utils import T, pairwise, partition_gen


@pytest.mark.parametrize(
    "slice_size, input_list, expected, ",
    [
        pytest.param(
            5,
            list(range(13)),
            [(0, 1, 2, 3, 4), (5, 6, 7, 8, 9), (10, 11, 12)],
            id="group_5_last_group_is_smaller",
        ),
        pytest.param(
            2,
            list(range(5)),
            [(0, 1), (2, 3), (4,)],
            id="group_2_last_group_is_smaller",
        ),
        pytest.param(
            2,
            list(range(4)),
            [(0, 1), (2, 3)],
            id="group_2_last_group_is_the_same",
        ),
        pytest.param(
            10,
            list(range(4)),
            [(0, 1, 2, 3)],
            id="only_one_group_if_list_is_not_bit_enough",
        ),
        pytest.param(
            3,
            [],
            [()],
            id="input_is_empty_returns_an_empty_list",
        ),
        pytest.param(
            5,
            list(range(13)),
            [(0, 1, 2, 3, 4), (5, 6, 7, 8, 9), (10, 11, 12)],
            id="group_5_using_generator",
        ),
    ],
)
def test_partition_gen(
    input_list: list[Any], expected: list[tuple[Any, ...]], slice_size: int
):
    # check returned result
    result = list(partition_gen(input_list, slice_size=slice_size))
    assert result == expected

    # check returned type
    for entry in result:
        assert type(entry) == tuple


@pytest.mark.parametrize(
    "input_iter, expected",
    [
        pytest.param([], [], id="0_elements"),
        pytest.param([1], [], id="1_element"),
        pytest.param([1, 2], [(1, 2)], id="2_elements"),
        pytest.param([1, 2, 3], [(1, 2), (2, 3)], id="3_elements"),
        pytest.param([1, 2, 3, 4], [(1, 2), (2, 3), (3, 4)], id="4_elements"),
    ],
)
def test_pairwise(input_iter: Iterable[T], expected: Iterable[tuple[T, T]]):
    assert list(pairwise(input_iter)) == expected
