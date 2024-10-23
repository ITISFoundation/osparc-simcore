from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .basic_types import IDStr


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class OrderBy(BaseModel):
    """inspired by Google AIP https://google.aip.dev/132#ordering"""

    field: IDStr = Field()
    direction: OrderDirection = Field(default=OrderDirection.ASC)

    model_config = ConfigDict(extra="forbid")
