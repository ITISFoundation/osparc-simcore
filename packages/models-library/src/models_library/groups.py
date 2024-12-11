from typing import Annotated, Final, NamedTuple, TypeAlias

from common_library.basic_types import DEFAULT_FACTORY
from common_library.groups_enums import GroupType as GroupType
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic.types import PositiveInt
from typing_extensions import TypedDict

from .basic_types import IDStr
from .users import UserID
from .utils.common_validators import create_enums_pre_validator

EVERYONE_GROUP_ID: Final[int] = 1

GroupID: TypeAlias = PositiveInt

__all__: tuple[str, ...] = ("GroupType",)


class Group(BaseModel):
    gid: PositiveInt
    name: str
    description: str
    group_type: Annotated[GroupType, Field(alias="type")]
    thumbnail: str | None

    inclusion_rules: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
        ),
    ] = DEFAULT_FACTORY

    _from_equivalent_enums = field_validator("group_type", mode="before")(
        create_enums_pre_validator(GroupType)
    )

    model_config = ConfigDict(populate_by_name=True)


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


class StandardGroupCreate(BaseModel):
    name: str
    description: str | None = None
    thumbnail: str | None = None
    inclusion_rules: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
            description="Maps user's column and regular expression",
        ),
    ] = DEFAULT_FACTORY


class StandardGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    inclusion_rules: dict[str, str] | None = None


class GroupAtDB(Group):
    # NOTE: deprecate and use `Group` instead
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
