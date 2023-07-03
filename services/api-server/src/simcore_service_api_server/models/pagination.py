""" Overrides models in fastapi_pagination

Usage:
    from fastapi_pagination.api import create_page
    from ...models.pagination import LimitOffsetPage, LimitOffsetParams

"""

from collections.abc import Sequence
from typing import Generic, TypeVar

from fastapi_pagination.limit_offset import LimitOffsetParams
from fastapi_pagination.links.limit_offset import LimitOffsetPage
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
)
from pydantic import Field, NonNegativeInt
from pydantic.generics import GenericModel

T = TypeVar("T")


class OnePage(GenericModel, Generic[T]):
    """
    A single page is used to envelope a small sequence that does not require
    pagination

    If total >  MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE, we should consider extending this
    entrypoint to proper pagination
    """

    items: Sequence[T]
    total: NonNegativeInt


# NOTE: same pagination limits and defaults as web-server
LimitOffsetPage = LimitOffsetPage.with_custom_options(
    limit=Field(
        DEFAULT_NUMBER_OF_ITEMS_PER_PAGE, ge=1, le=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    )
)

assert LimitOffsetParams  # nosec

__all__: tuple[str, ...] = (
    "LimitOffsetPage",
    "LimitOffsetParams",
    "MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE",
    "OnePage",
)
