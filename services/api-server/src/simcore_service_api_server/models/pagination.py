"""Overrides models in fastapi_pagination

Usage:
    from fastapi_pagination.api import create_page
    from ...models.pagination import LimitOffsetPage, LimitOffsetParams

"""

from collections.abc import Sequence
from typing import Any, TypeAlias, TypeVar

from fastapi import Query
from fastapi_pagination.customization import ClsNamespace, CustomizedPage, PageCls, UseName, UseParamsFields
from fastapi_pagination.limit_offset import LimitOffsetPage as _LimitOffsetPage
from fastapi_pagination.links import UseLimitOffsetLinks
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    MINIMUM_NUMBER_OF_ITEMS_PER_PAGE,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    ValidationInfo,
    computed_field,
    field_validator,
)

T = TypeVar("T")


class Links(BaseModel):
    first: str | None = Field(default=..., examples=["/api/v1/users?limit=1&offset=0"])
    last: str | None = Field(default=..., examples=["/api/v1/users?limit=1&offset=10"])
    next: str | None = Field(default=..., examples=["/api/v1/users?limit=1&offset=2"])
    prev: str | None = Field(default=..., examples=["/api/v1/users?limit=1&offset=0"])
    self: str | None = Field(default=..., examples=["/api/v1/users?limit=1&offset=1"])


class _UseRequiredLimitOffsetLinks(UseLimitOffsetLinks):
    def customize_page_ns(self, page_cls: PageCls, ns: ClsNamespace) -> None:
        def _resolve_required_links(page: _LimitOffsetPage[Any]) -> Links:
            return Links.model_validate(self.resolve_links(page), from_attributes=True)

        assert issubclass(page_cls, _LimitOffsetPage)  # nosec
        ns[self.field] = computed_field(return_type=Links)(_resolve_required_links)


Page = CustomizedPage[
    _LimitOffsetPage[T],
    _UseRequiredLimitOffsetLinks(),
    # Customizes the default and maximum to fit those of the web-server. It simplifies interconnection
    UseParamsFields(
        limit=Query(
            # NOTE: in sync with PageLimitInt
            DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
            ge=MINIMUM_NUMBER_OF_ITEMS_PER_PAGE,
            le=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
            description="Page size limit",
        )
    ),
    # Renames class for the openapi.json to make the python-client's name models shorter
    UseName(name="Page"),
]

# FastAPI Depends requires the concrete runtime class instead of a lazy TypeAliasType.
PaginationParams: TypeAlias = Page.__params_type__  # type: ignore  # noqa: UP040


class OnePage[T](BaseModel):
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
    "MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE",
    "OnePage",
    "Page",
    "PaginationParams",
)
