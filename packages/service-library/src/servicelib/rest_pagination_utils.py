from math import ceil
from typing import Any, Dict, List, Optional

from pydantic import AnyHttpUrl, BaseModel, Extra, Field, PositiveInt, conint, validator
from yarl import URL


class PageMetaInfoLimitOffset(BaseModel):
    total: conint(ge=0)
    count: conint(ge=0)
    offset: conint(ge=0) = 0
    limit: PositiveInt

    class Config:
        extra = Extra.forbid


class PageLinks(BaseModel):
    self: AnyHttpUrl
    first: AnyHttpUrl
    prev: Optional[AnyHttpUrl]
    next: Optional[AnyHttpUrl]
    last: AnyHttpUrl

    class Config:
        extra = Extra.forbid


class PageResponseLimitOffset(BaseModel):
    meta: PageMetaInfoLimitOffset = Field(alias="_meta")
    links: PageLinks = Field(alias="_links")
    data: List[Any]

    class Config:
        extra = Extra.forbid

    @validator("data", always=True, pre=True)
    @classmethod
    def convert_none_to_empty_list(cls, v):
        if v is None:
            v = list()
        return v

    @validator("data", always=True, pre=True)
    @classmethod
    def check_data_size_smaller_than_limit(cls, v, values):
        limit = values["meta"].limit
        if len(v) > limit:
            raise ValueError(f"container size must be smaller than limit [{limit}]")
        return v

    @classmethod
    def paginate_data(
        cls,
        data: List[Any],
        request_url: URL,
        total: int,
        limit: int,
        offset: int,
    ) -> "PageResponseLimitOffset":
        last_page = ceil(total / limit) - 1

        return PageResponseLimitOffset(
            _meta=PageMetaInfoLimitOffset(
                total=total, count=len(data), limit=limit, offset=offset
            ),
            _links=PageLinks(
                self=f"{request_url}",
                first=f"{request_url.update_query({'offset': 0})}",
                prev=f"{request_url.update_query({'offset': offset - 1})}"
                if offset
                else None,
                next=f"{request_url.update_query({'offset': offset + 1})}"
                if offset < last_page
                else None,
                last=f"{request_url.update_query({'offset': last_page})}",
            ),
            data=data,
        )
