import enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.types import PositiveInt

from .utils.common_validators import create_enums_pre_validator

EVERYONE_GROUP_ID: Final[int] = 1


class GroupTypeInModel(str, enum.Enum):
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

    _from_equivalent_enums = field_validator("group_type", mode="before")(
        create_enums_pre_validator(GroupTypeInModel)
    )


class GroupAtDB(Group):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "gid": 218,
                "name": "Friends group",
                "description": "Joey, Ross, Rachel, Monica, Phoeby and Chandler",
                "type": "standard",
                "thumbnail": "https://image.flaticon.com/icons/png/512/23/23374.png",
            }
        },
    )
