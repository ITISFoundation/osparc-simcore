from enum import Enum

from pydantic import BaseModel, Field


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class OrderBy(BaseModel):
    """inspired by Google AIP https://google.aip.dev/132#ordering"""

    field: str = Field(default=None)
    direction: OrderDirection = Field(default=OrderDirection.DESC)

    class Config:
        extra = "forbid"
