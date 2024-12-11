from contextlib import suppress
from typing import Annotated, Any, Self, TypeVar

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import (
    AnyHttpUrl,
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from ..emails import LowerCaseEmailStr
from ..groups import (
    AccessRightsDict,
    Group,
    GroupID,
    GroupMember,
    StandardGroupCreate,
    StandardGroupUpdate,
)
from ..users import UserID, UserNameID
from ..utils.common_validators import create__check_only_one_is_set__root_validator
from ._base import InputSchema, OutputSchema

S = TypeVar("S", bound=BaseModel)


def _rename_keys(source: dict, name_map: dict[str, str]) -> dict[str, Any]:
    return {name_map.get(k, k): v for k, v in source.items()}


class GroupAccessRights(BaseModel):
    """
    defines acesss rights for the user
    """

    read: bool
    write: bool
    delete: bool

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"read": True, "write": False, "delete": False},
                {"read": True, "write": True, "delete": False},
                {"read": True, "write": True, "delete": True},
            ]
        }
    )


class GroupGet(OutputSchema):
    gid: GroupID = Field(..., description="the group ID")
    label: str = Field(..., description="the group name")
    description: str = Field(..., description="the group description")
    thumbnail: AnyUrl | None = Field(
        default=None, description="url to the group thumbnail"
    )
    access_rights: GroupAccessRights = Field(..., alias="accessRights")

    inclusion_rules: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
            alias="inclusionRules",
            deprecated=True,
        ),
    ] = DEFAULT_FACTORY

    @classmethod
    def from_model(cls, group: Group, access_rights: AccessRightsDict) -> Self:
        # Merges both service models into this schema
        return cls.model_validate(
            {
                **_rename_keys(
                    group.model_dump(
                        include={
                            "gid",
                            "name",
                            "description",
                            "thumbnail",
                        },
                        exclude={"access_rights", "inclusion_rules"},
                        exclude_unset=True,
                        by_alias=False,
                    ),
                    name_map={
                        "name": "label",
                    },
                ),
                "access_rights": access_rights,
            }
        )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "gid": "27",
                    "label": "A user",
                    "description": "A very special user",
                    "thumbnail": "https://placekitten.com/10/10",
                    "accessRights": {"read": True, "write": False, "delete": False},
                },
                {
                    "gid": 1,
                    "label": "ITIS Foundation",
                    "description": "The Foundation for Research on Information Technologies in Society",
                    "accessRights": {"read": True, "write": False, "delete": False},
                },
                {
                    "gid": "0",
                    "label": "All",
                    "description": "Open to all users",
                    "accessRights": {"read": True, "write": True, "delete": True},
                },
                {
                    "gid": 5,
                    "label": "SPARCi",
                    "description": "Stimulating Peripheral Activity to Relieve Conditions",
                    "thumbnail": "https://placekitten.com/15/15",
                    "accessRights": {"read": True, "write": True, "delete": True},
                },
            ]
        }
    )

    @field_validator("thumbnail", mode="before")
    @classmethod
    def _sanitize_legacy_data(cls, v):
        if v:
            # Enforces null if thumbnail is not valid URL or empty
            with suppress(ValidationError):
                return TypeAdapter(AnyHttpUrl).validate_python(v)
        return None


class GroupCreate(InputSchema):
    label: str
    description: str
    thumbnail: AnyUrl | None = None

    def to_model(self) -> StandardGroupCreate:
        data = _rename_keys(
            self.model_dump(
                mode="json",
                # NOTE: intentionally inclusion_rules are not exposed to the REST api
                include={"label", "description", "thumbnail"},
                exclude_unset=True,
            ),
            name_map={"label": "name"},
        )
        return StandardGroupCreate(**data)


class GroupUpdate(InputSchema):
    label: str | None = None
    description: str | None = None
    thumbnail: AnyUrl | None = None

    def to_model(self) -> StandardGroupUpdate:
        data = _rename_keys(
            self.model_dump(
                mode="json",
                # NOTE: intentionally inclusion_rules are not exposed to the REST api
                include={"label", "description", "thumbnail"},
                exclude_unset=True,
            ),
            name_map={"label": "name"},
        )
        return StandardGroupUpdate(**data)


class MyGroupsGet(OutputSchema):
    me: GroupGet
    organizations: list[GroupGet] | None = None
    all: GroupGet
    product: GroupGet | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "me": {
                    "gid": "27",
                    "label": "A user",
                    "description": "A very special user",
                    "accessRights": {"read": True, "write": True, "delete": True},
                },
                "organizations": [
                    {
                        "gid": "15",
                        "label": "ITIS Foundation",
                        "description": "The Foundation for Research on Information Technologies in Society",
                        "accessRights": {
                            "read": True,
                            "write": False,
                            "delete": False,
                        },
                    },
                    {
                        "gid": "16",
                        "label": "Blue Fundation",
                        "description": "Some foundation",
                        "accessRights": {
                            "read": True,
                            "write": False,
                            "delete": False,
                        },
                    },
                ],
                "all": {
                    "gid": "0",
                    "label": "All",
                    "description": "Open to all users",
                    "accessRights": {"read": True, "write": False, "delete": False},
                },
            }
        }
    )


class GroupUserGet(BaseModel):
    # OutputSchema

    # Identifiers
    id: Annotated[UserID | None, Field(description="the user's id")] = None
    user_name: Annotated[UserNameID, Field(alias="userName")]
    gid: Annotated[
        GroupID | None,
        Field(description="the user primary gid"),
    ] = None

    # Private Profile
    login: Annotated[
        LowerCaseEmailStr | None,
        Field(description="the user's email, if privacy settings allows"),
    ] = None
    first_name: Annotated[
        str | None, Field(description="If privacy settings allows")
    ] = None
    last_name: Annotated[
        str | None, Field(description="If privacy settings allows")
    ] = None
    gravatar_id: Annotated[
        str | None, Field(description="the user gravatar id hash", deprecated=True)
    ] = None

    # Access Rights
    access_rights: GroupAccessRights = Field(..., alias="accessRights")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "1",
                "userName": "mrmith",
                "login": "mr.smith@matrix.com",
                "first_name": "Mr",
                "last_name": "Smith",
                "gravatar_id": "a1af5c6ecc38e81f29695f01d6ceb540",
                "gid": "3",
                "accessRights": {
                    "read": True,
                    "write": False,
                    "delete": False,
                },
            }
        },
    )

    @classmethod
    def from_model(cls, user: GroupMember) -> Self:
        return cls.model_validate(
            {
                "id": user.id,
                "user_name": user.name,
                "login": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "gid": user.primary_gid,
                "access_rights": user.access_rights,
            }
        )


class GroupUserAdd(InputSchema):
    """
    Identify the user with either `email` or `uid` — only one.
    """

    uid: UserID | None = None
    user_name: Annotated[UserNameID | None, Field(alias="userName")] = None
    email: Annotated[
        LowerCaseEmailStr | None,
        Field(
            description="Accessible only if the user has opted to share their email in privacy settings"
        ),
    ] = None

    _check_uid_or_email = model_validator(mode="after")(
        create__check_only_one_is_set__root_validator(["uid", "email", "user_name"])
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"uid": 42},
                {"email": "foo@email.com"},
            ]
        }
    )


class GroupUserUpdate(InputSchema):
    # NOTE: since it is a single item, it is required. Cannot
    # update for the moment partial attributes e.g. {read: False}
    access_rights: GroupAccessRights

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "accessRights": {
                    "read": True,
                    "write": False,
                    "delete": False,
                },
            }
        }
    )
