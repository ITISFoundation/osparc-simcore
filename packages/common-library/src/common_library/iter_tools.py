from collections.abc import AsyncIterator
from typing import Protocol


class GetPageCallable(Protocol):
    async def __call__(
        self, *args: object, offset: int, limit: int, **kwargs: object
    ) -> tuple[list, int]:
        ...


async def iter_pages(
    get_page_and_total_count: GetPageCallable,
    *args,
    offset: int = 0,
    limit: int = 100,
    **kwargs,
) -> AsyncIterator[list]:
    """
    Asynchronous generator that yields offsets for paginated API calls
    """
    total_number_of_items = None

    if limit <= 0:
        msg = f"{limit=} must be positive"
        raise ValueError(msg)
    if offset < 0:
        msg = f"{offset=} must be non-negative"
        raise ValueError(msg)

    while total_number_of_items is None or offset < total_number_of_items:
        items, total_number_of_items = await get_page_and_total_count(
            *args, offset=offset, limit=limit, **kwargs
        )

        assert len(items) <= limit  # nosec
        assert len(items) <= total_number_of_items  # nosec

        yield items

        offset += limit
