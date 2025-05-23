from collections.abc import Iterable
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt


class PageParams(BaseModel):
    offset_initial: Annotated[NonNegativeInt, Field(frozen=True)] = 0
    offset_current: NonNegativeInt = 0  # running offset
    limit: Annotated[PositiveInt, Field(frozen=True)]
    total_number_of_items: int | None = None

    model_config = ConfigDict(validate_assignment=True)

    @property
    def offset(self) -> NonNegativeInt:
        return self.offset_current

    def has_items_left(self) -> bool:
        return (
            self.total_number_of_items is None
            or self.offset_current < self.total_number_of_items
        )

    def total_number_of_pages(self) -> NonNegativeInt:
        assert self.total_number_of_items  # nosec
        num_items = self.total_number_of_items - self.offset_initial
        return num_items // self.limit + (1 if num_items % self.limit else 0)


def iter_pagination_params(
    *,
    limit: PositiveInt,
    offset: NonNegativeInt = 0,
    total_number_of_items: NonNegativeInt | None = None,
) -> Iterable[PageParams]:

    kwargs = {}
    if total_number_of_items:
        kwargs["total_number_of_items"] = total_number_of_items

    page_params = PageParams(
        offset_initial=offset, offset_current=offset, limit=limit, **kwargs
    )

    assert page_params.offset_current == page_params.offset_initial  # nosec

    total_count_before = page_params.total_number_of_items
    page_index = 0

    while page_params.has_items_left():

        yield page_params

        if page_params.total_number_of_items is None:
            msg = "Must be updated at least before the first iteration, i.e. page_args.total_number_of_items = total_count"
            raise RuntimeError(msg)

        if (
            total_count_before
            and total_count_before != page_params.total_number_of_items
        ):
            msg = (
                f"total_number_of_items cannot change on every iteration: before={total_count_before}, now={page_params.total_number_of_items}."
                "WARNING: the size of the paginated collection might be changing while it is being iterated?"
            )
            raise RuntimeError(msg)

        if page_index == 0:
            total_count_before = page_params.total_number_of_items

        page_params.offset_current += limit
        assert page_params.offset == page_params.offset_current  # nosec
