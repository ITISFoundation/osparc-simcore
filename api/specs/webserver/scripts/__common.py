from typing import Generic, List, Optional, Tuple, TypeVar

from pydantic import PositiveInt
from pydantic.fields import Field
from pydantic.generics import GenericModel
from pydantic.main import BaseModel, Extra
from pydantic.networks import AnyHttpUrl
from pydantic.types import NonNegativeInt, constr

# see https://google.aip.dev/122
ResourceName = constr(regex=r"^(.+)\/([^\/]+)$")
ResourceID = constr(min_length=1, max_length=63)
UserSetResourceID = constr(
    regex=r"^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", min_length=1, max_length=63
)
CollectionID = constr(regex=r"[a-z][a-zA-Z0-9]*")


class Resource(BaseModel):
    # e.g. format: publishers/{publisher}/books/{book}
    name: ResourceName = Field(...)


# PAGINATION ----------------------------------------


class PageMetaInfoLimitOffset(BaseModel):
    limit: PositiveInt = 20
    total: NonNegativeInt
    offset: NonNegativeInt = 0
    count: NonNegativeInt


class PageLinks(BaseModel):
    self: AnyHttpUrl
    first: AnyHttpUrl
    prev: Optional[AnyHttpUrl]
    next: Optional[AnyHttpUrl]
    last: AnyHttpUrl

    class Config:
        extra = Extra.forbid


ItemT = TypeVar("ItemT")


class Page(GenericModel, Generic[ItemT]):
    meta: PageMetaInfoLimitOffset = Field(alias="_meta")
    links: PageLinks = Field(alias="_links")
    data: List[ItemT]


DataT = TypeVar("DataT")


class Error(BaseModel):
    code: int
    message: str


class Envelope(GenericModel, Generic[DataT]):
    data: Optional[DataT]
    error: Optional[Error]


__all__: Tuple[str, ...] = ("Page", "Envelope")
