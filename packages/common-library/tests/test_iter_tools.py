# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
from collections.abc import Callable

import pytest
from common_library.iter_tools import iter_pages


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
async def test_iter_pages(
    limit: int, offset: int, get_page: Callable, all_items: list[int]
):

    last_page = [None] * 2
    async for page_items in iter_pages(get_page, offset=offset, limit=limit):
        assert len(page_items) <= limit

        assert set(last_page) != set(page_items)
        last_page = list(page_items)

        # contains sub-sequence
        assert str(page_items)[1:-1] in str(all_items)[1:-1]


@pytest.mark.parametrize("limit", [-1, 0])
@pytest.mark.parametrize("offset", [-1])
async def test_iter_pages_invalid(limit: int, offset: int, get_page: Callable):

    with pytest.raises(ValueError, match="must be"):  # noqa: PT012
        async for _ in iter_pages(get_page, offset=offset, limit=limit):
            pass
