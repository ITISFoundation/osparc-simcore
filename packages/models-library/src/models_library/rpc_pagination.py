from math import ceil
from typing import Any, ClassVar, Generic

from pydantic import Extra, Field

from .rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    ItemT,
    Page,
    PageLimitInt,
    PageMetaInfoLimitOffset,
    PageQueryParameters,
    PageRefs,
)

assert DEFAULT_NUMBER_OF_ITEMS_PER_PAGE  # nosec
assert MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE  # nosec
assert PageLimitInt  # nosec

__all__: tuple[str, ...] = (
    "DEFAULT_NUMBER_OF_ITEMS_PER_PAGE",
    "MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE",
    "PageLimitInt",
    "PageMetaInfoLimitOffset",
)


class PageRefsParams(PageRefs[PageQueryParameters]):
    @classmethod
    def create(cls, total: int, limit: int, offset: int) -> "PageRefsParams":
        last_page = ceil(total / limit) - 1
        return cls.parse_obj(
            {
                "self": {"offset": offset, "limit": limit},
                "first": {"offset": 0, "limit": limit},
                "prev": {"offset": max(offset - limit, 0), "limit": limit}
                if offset > 0
                else None,
                "next": {
                    "offset": min(offset + limit, last_page * limit),
                    "limit": limit,
                }
                if offset < (last_page * limit)
                else None,
                "last": {"offset": last_page * limit, "limit": limit},
            }
        )


class PageRpc(Page[ItemT], Generic[ItemT]):

    links: PageRefsParams = Field(alias="_links")  # type: ignore

    @classmethod
    def create(
        cls,
        chunk: list[Any],
        *,
        total: int,
        limit: int,
        offset: int,
    ):
        return cls(
            _meta=PageMetaInfoLimitOffset(
                total=total, count=len(chunk), limit=limit, offset=offset
            ),
            _links=PageRefsParams.create(total=total, limit=limit, offset=offset),
            data=chunk,
        )

    class Config:
        extra = Extra.forbid

        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # first page Page[str]
                {
                    "_meta": {"total": 7, "count": 4, "limit": 4, "offset": 0},
                    "_links": {
                        "self": {"offset": 0, "limit": 4},
                        "first": {"offset": 0, "limit": 4},
                        "prev": None,
                        "next": {"offset": 1, "limit": 4},
                        "last": {"offset": 1, "limit": 4},
                    },
                    "data": ["data 1", "data 2", "data 3", "data 4"],
                },
                # second and last page
                {
                    "_meta": {"total": 7, "count": 3, "limit": 4, "offset": 1},
                    "_links": {
                        "self": {"offset": 1, "limit": 4},
                        "first": {"offset": 0, "limit": 4},
                        "prev": {"offset": 0, "limit": 4},
                        "next": None,
                        "last": {"offset": 1, "limit": 4},
                    },
                    "data": ["data 5", "data 6", "data 7"],
                },
            ]
        }
