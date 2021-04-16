from math import ceil
from typing import Any, Dict, List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, PositiveInt, conint, validator
from yarl import URL


class PageMetaInfoLimitOffset(BaseModel):
    total: conint(ge=0)
    count: conint(ge=0)
    offset: conint(ge=0) = 0
    limit: PositiveInt


class PageLinks(BaseModel):
    self: AnyHttpUrl
    first: AnyHttpUrl
    prev: Optional[AnyHttpUrl]
    next: Optional[AnyHttpUrl]
    last: AnyHttpUrl


class PageResponseLimitOffset(BaseModel):
    meta: PageMetaInfoLimitOffset = Field(alias="_meta")
    links: PageLinks = Field(alias="_links")
    data: List[Any]

    @validator("data")
    @classmethod
    def check_data_size_smaller_than_limit(cls, v, values):
        limit = values["meta"]["limit"]
        if len(v) > limit:
            raise ValueError(f"container size must be smaller than limit [{limit}]")

    @classmethod
    def paginate_data(
        data: List[Any],
        request_url: URL,
        total: int,
        limit: int,
        offset: int,
    ) -> "PageResponseLimitOffset":
        last_page = ceil(total / limit) - 1

        return PageResponseLimitOffset(
            data=data,
            meta=PageMetaInfoLimitOffset(
                total=total, count=len(data), limit=limit, offset=offset
            ),
            links=PageLinks(
                self=request_url,
                first=request_url.update_query({"offset": 0}),
                prev=request_url.update_query({"offset": offset - 1})
                if offset
                else None,
                next=request_url.update_query({"offset": offset + 1})
                if offset < last_page
                else None,
                last=request_url.update_query({"offset": last_page}),
            ),
        ).dict(by_alias=True)
