""" Overrides models in fastapi_pagination

Usage:
    from fastapi_pagination.api import create_page
    from ...models.pagination import LimitOffsetPage, LimitOffsetParams

"""

from collections.abc import Sequence
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar

from fastapi_pagination.limit_offset import LimitOffsetParams
from fastapi_pagination.links.limit_offset import (
    LimitOffsetPage as _FastApiLimitOffsetPage,
)
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
)
from models_library.utils.pydantic_tools_extension import FieldNotRequired
from pydantic import Field, NonNegativeInt, validator
from pydantic.generics import GenericModel

T = TypeVar("T")

# NOTE: same pagination limits and defaults as web-server
Page = _FastApiLimitOffsetPage.with_custom_options(
    limit=Field(
        DEFAULT_NUMBER_OF_ITEMS_PER_PAGE, ge=1, le=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    )
)
# NOTE: Renamed to make shorter clients name models
Page.__name__ = "Page"

PaginationParams: TypeAlias = LimitOffsetParams


class OnePage(GenericModel, Generic[T]):
    """
    A single page is used to envelope a small sequence that does not require
    pagination

    If total >  MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE, we should consider extending this
    entrypoint to proper pagination
    """

    items: Sequence[T]
    total: NonNegativeInt = FieldNotRequired()

    @validator("total", pre=True)
    @classmethod
    def check_total(cls, v, values):
        items = values["items"]
        if v is None:
            return len(items)

        if v != len(items):
            msg = f"In one page total:{v} == len(items):{len(items)}"
            raise ValueError(msg)

        return v

    class Config:
        frozen = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "total": 1,
                    "items": ["one"],
                },
                {
                    "items": ["one"],
                },
            ],
        }


__all__: tuple[str, ...] = (
    "PaginationParams",
    "MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE",
    "OnePage",
    "Page",
)
