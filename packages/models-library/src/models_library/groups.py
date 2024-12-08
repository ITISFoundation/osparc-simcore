import enum
from typing import Annotated, Final, NamedTuple, TypeAlias, TypedDict

from common_library.basic_types import DEFAULT_FACTORY
from models_library.basic_types import IDStr
from models_library.groups import Group
from models_library.users import GroupID, UserID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
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
    group_type: Annotated[GroupTypeInModel, Field(alias="type")]
    thumbnail: str | None

    inclusion_rules: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
        ),
    ] = DEFAULT_FACTORY

    _from_equivalent_enums = field_validator("group_type", mode="before")(
        create_enums_pre_validator(GroupTypeInModel)
    )


class AccessRightsDict(TypedDict):
    read: bool
    write: bool
    delete: bool


GroupInfoTuple: TypeAlias = tuple[Group, AccessRightsDict]


class GroupsByTypeTuple(NamedTuple):
    primary: GroupInfoTuple | None
    standard: list[GroupInfoTuple]
    everyone: GroupInfoTuple | None


class GroupMember(BaseModel):
    # identifiers
    id: UserID
    name: IDStr
    primary_gid: GroupID

    # private profile
    email: EmailStr | None
    first_name: str | None
    last_name: str | None

    # group access
    access_rights: AccessRightsDict

    model_config = ConfigDict(from_attributes=True)


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
