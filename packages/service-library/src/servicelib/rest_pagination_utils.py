from math import ceil
from typing import Any, List, Optional

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    Extra,
    Field,
    NonNegativeInt,
    PositiveInt,
    validator,
)
from yarl import URL


class PageMetaInfoLimitOffset(BaseModel):
    limit: PositiveInt
    total: NonNegativeInt
    offset: NonNegativeInt = 0
    count: NonNegativeInt

    @validator("offset", always=True)
    @classmethod
    def check_offset(cls, v, values):
        if v >= values["total"]:
            raise ValueError(
                f"offset {v} cannot be equal or bigger than total {values['total']}, please check"
            )
        return v

    @validator("count", always=True)
    @classmethod
    def check_count(cls, v, values):
        if v > values["limit"]:
            raise ValueError(
                f"count {v} bigger than limit {values['limit']}, please check"
            )
        if v > values["total"]:
            raise ValueError(
                f"count {v} bigger than expected total {values['total']}, please check"
            )
        if (values["offset"] + v) > values["total"]:
            raise ValueError(
                f"offset {values['offset']} + count {v} is bigger than allowed total {values['total']}, please check"
            )
        return v

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
    def check_data_compatible_with_meta(cls, v, values):
        if len(v) != values["meta"].count:
            raise ValueError(
                f"container size must be equal to count [{values['meta'].count}]"
            )
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
                prev=f"{request_url.update_query({'offset': max(offset - limit, 0), 'limit': limit})}"
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
