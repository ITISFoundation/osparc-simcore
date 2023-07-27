from enum import auto
from typing import Any, ClassVar, Final

from pydantic import BaseModel, Field
from pydantic.types import PositiveInt

from .utils.enums import StrAutoEnum

EVERYONE_GROUP_ID: Final[int] = 1


class GroupType(StrAutoEnum):
    """
    standard: standard group, e.g. any group that is not a primary group or special group such as the everyone group
    primary: primary group, e.g. the primary group is the user own defined group that typically only contain the user (same as in linux)
    everyone: the only group for all users
    """

    STANDARD = auto()
    PRIMARY = auto()
    EVERYONE = auto()


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
