from enum import Enum

from models_library.basic_types import IDStr
from pydantic import BaseModel, Field


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class OrderBy(BaseModel):
    """inspired by Google AIP https://google.aip.dev/132#ordering"""

    field: IDStr
    direction: OrderDirection = Field(default=OrderDirection.ASC)

    class Config:
        extra = "forbid"
