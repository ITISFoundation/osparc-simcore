from math import ceil
from typing import Any, List, Optional

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
                self=f"{request_url.update_query({'offset': offset, 'limit': limit})}",
                first=f"{request_url.update_query({'offset': 0, 'limit': limit})}",
                prev=f"{request_url.update_query({'offset': min(offset - limit, 0), 'limit': limit})}"
                if offset > 0
                else None,
                next=f"{request_url.update_query({'offset': min(offset + limit, last_page * limit), 'limit': limit})}"
                if offset < (last_page * limit)
                else None,
                last=f"{request_url.update_query({'offset': last_page * limit, 'limit': limit})}",
            ),
            data=data,
        )

    class Config:
        extra = Extra.forbid

        schema_extra = {
            "examples": [
                # first page
                {
                    "_meta": {"total": 7, "count": 4, "limit": 4, "offset": 0},
                    "_links": {
                        "self": "http://osparc.io/v2/listing?offset=0&limit=4",
                        "first": "http://osparc.io/v2/listing?offset=0&limit=4",
                        "prev": None,
                        "next": "http://osparc.io/v2/listing?offset=1&limit=4",
                        "last": "http://osparc.io/v2/listing?offset=1&limit=4",
                    },
                    "data": ["data 1", "data 2", "data 3", "data 4"],
                },
                # second and last page
                {
                    "_meta": {"total": 7, "count": 3, "limit": 4, "offset": 1},
                    "_links": {
                        "self": "http://osparc.io/v2/listing?offset=1&limit=4",
                        "first": "http://osparc.io/v2/listing?offset=0&limit=4",
                        "prev": "http://osparc.io/v2/listing?offset=0&limit=4",
                        "next": None,
                        "last": "http://osparc.io/v2/listing?offset=1&limit=4",
                    },
                    "data": ["data 5", "data 6", "data 7"],
                },
            ]
        }
