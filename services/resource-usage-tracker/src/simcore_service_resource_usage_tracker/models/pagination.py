""" Overrides models in fastapi_pagination

Usage:
    from fastapi_pagination.api import create_page
    from ...models.pagination import LimitOffsetPage, LimitOffsetParams

"""

from fastapi import Query
from fastapi_pagination.limit_offset import LimitOffsetParams
from fastapi_pagination.links.limit_offset import LimitOffsetPage
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
)
from pydantic import Field

#
# NOTE: same pagination limits and defaults as web-server
LimitOffsetPage = LimitOffsetPage.with_custom_options(
    limit=Field(
        DEFAULT_NUMBER_OF_ITEMS_PER_PAGE, ge=1, le=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    )
)


class LimitOffsetParamsWithDefault(LimitOffsetParams):
    limit: int = Query(
        DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        ge=1,
        le=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
        description="Page size limit",
    )


__all__: tuple[str, ...] = ("LimitOffsetPage",)
