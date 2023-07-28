import enum
from typing import Any, ClassVar, Final

from models_library.utils.common_validators import (
    create_transform_from_equivalent_enums,
)
from pydantic import BaseModel, Field, validator
from pydantic.types import PositiveInt

EVERYONE_GROUP_ID: Final[int] = 1


class GroupTypeInModel(str, enum.Enum):  # noqa: SLOT000
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
    group_type: GroupTypeInModel = Field(..., alias="type")
    thumbnail: str | None

    _from_equivalent_enums = validator("group_type", allow_reuse=True, pre=True)(
        create_transform_from_equivalent_enums(GroupTypeInModel)
    )


class GroupAtDB(Group):
    class Config:
        orm_mode = True

        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "gid": 218,
                "name": "Friends group",
                "description": "Joey, Ross, Rachel, Monica, Phoeby and Chandler",
                "type": "standard",
                "thumbnail": "https://image.flaticon.com/icons/png/512/23/23374.png",
            }
        }
