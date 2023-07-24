import enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field
from pydantic.types import PositiveInt


class GroupType(enum.Enum):
    """
    standard: standard group, e.g. any group that is not a primary group or special group such as the everyone group
    primary: primary group, e.g. the primary group is the user own defined group that typically only contain the user (same as in linux)
    everyone: the only group for all users
    """

    STANDARD = "standard"
    PRIMARY = "primary"
    EVERYONE = "everyone"


class Group(BaseModel):
    gid: PositiveInt
    name: str
    description: str
    group_type: GroupType = Field(..., alias="type")
    thumbnail: str | None


class GroupAtDB(Group):
    class Config:
        orm_mode = True

        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "gid": 218,
                "name": "Friends group",
                "description": "Joey, Ross, Rachel, Monica, Phoeby and Chandler",
                "type": "STANDARD",
                "thumbnail": "https://image.flaticon.com/icons/png/512/23/23374.png",
            }
        }
