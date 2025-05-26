# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
from collections.abc import Callable

import pytest
from common_library.pagination_tools import iter_pagination_params
from pydantic import ValidationError


@pytest.fixture
def all_items() -> list[int]:
    return list(range(11))


@pytest.fixture
async def get_page(all_items: list[int]) -> Callable:
    async def _get_page(offset, limit) -> tuple[list[int], int]:
        await asyncio.sleep(0)
        return all_items[offset : offset + limit], len(all_items)

    return _get_page


@pytest.mark.parametrize("limit", [2, 3, 5])
@pytest.mark.parametrize("offset", [0, 1, 5])
async def test_iter_pages_args(
    limit: int, offset: int, get_page: Callable, all_items: list[int]
):

    last_page = [None] * limit

    num_items = len(all_items) - offset
    expected_num_pages = num_items // limit + (1 if num_items % limit else 0)

    num_pages = 0
    page_args = None
    for page_index, page_args in enumerate(
        iter_pagination_params(offset=offset, limit=limit)
    ):

        page_items, page_args.total_number_of_items = await get_page(
            page_args.offset_current, page_args.limit
        )

        assert set(last_page) != set(page_items)
        last_page = list(page_items)

        # contains sub-sequence
        assert str(page_items)[1:-1] in str(all_items)[1:-1]

        num_pages = page_index + 1

    assert last_page[-1] == all_items[-1]
    assert num_pages == expected_num_pages

    assert page_args is not None
    assert not page_args.has_items_left()
    assert page_args.total_number_of_pages() == num_pages


@pytest.mark.parametrize("limit", [-1, 0])
@pytest.mark.parametrize("offset", [-1])
def test_iter_pages_args_invalid(limit: int, offset: int):

    with pytest.raises(ValidationError):  # noqa: PT012
        for _ in iter_pagination_params(offset=offset, limit=limit):
            pass


def test_fails_if_total_number_of_items_not_set():
    with pytest.raises(  # noqa: PT012
        RuntimeError,
        match="page_args.total_number_of_items = total_count",
    ):
        for _ in iter_pagination_params(offset=0, limit=2):
            pass


def test_fails_if_total_number_of_items_changes():
    with pytest.raises(  # noqa: PT012
        RuntimeError,
        match="total_number_of_items cannot change on every iteration",
    ):
        for page_params in iter_pagination_params(
            offset=0, limit=2, total_number_of_items=4
        ):
            assert page_params.total_number_of_items == 4
            page_params.total_number_of_items += 1
