""" Overrides models in fastapi_pagination

Usage:
    from fastapi_pagination.api import create_page
    from ...models.pagination import LimitOffsetPage, LimitOffsetParams

"""

from collections.abc import Sequence
from typing import Generic, TypeAlias, TypeVar

from fastapi import Query
from fastapi_pagination.customization import CustomizedPage, UseName, UseParamsFields
from fastapi_pagination.limit_offset import LimitOffsetParams as _LimitOffsetParams
from fastapi_pagination.links import LimitOffsetPage as _LimitOffsetPage
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    ValidationInfo,
    field_validator,
)

T = TypeVar("T")

Page = CustomizedPage[
    _LimitOffsetPage[T],
    # Customizes the default and maximum to fit those of the web-server. It simplifies interconnection
    UseParamsFields(
        limit=Query(
            DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
            ge=1,
            le=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
            description="Page size limit",
        )
    ),
    # Renames class for the openapi.json to make the python-client's name models shorter
    UseName(name="Page"),
]

PaginationParams: TypeAlias = _LimitOffsetParams


class OnePage(BaseModel, Generic[T]):
    """
    A single page is used to envelope a small sequence that does not require
    pagination

    If total >  MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE, we should consider extending this
    entrypoint to proper pagination
    """

    items: Sequence[T]
    total: NonNegativeInt | None = Field(default=None, validate_default=True)

    @field_validator("total", mode="before")
    @classmethod
    def _check_total(cls, v, info: ValidationInfo):
        items = info.data.get("items", [])
        if v is None:
            return len(items)

        if v != len(items):
            msg = f"In one page total:{v} == len(items):{len(items)}"
            raise ValueError(msg)

        return v

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "total": 1,
                    "items": ["one"],
                },
                {
                    "items": ["one"],
                },
            ],
        },
    )


__all__: tuple[str, ...] = (
    "PaginationParams",
    "MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE",
    "OnePage",
    "Page",
)
