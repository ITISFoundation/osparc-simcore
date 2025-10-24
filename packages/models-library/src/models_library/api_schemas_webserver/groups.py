from contextlib import suppress
from typing import Annotated, Self, TypeVar

from common_library.basic_types import DEFAULT_FACTORY
from common_library.dict_tools import remap_keys
from models_library.string_types import DescriptionSafeStr, NameSafeStr
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
from pydantic.config import JsonDict

from ..emails import LowerCaseEmailStr
from ..groups import (
    EVERYONE_GROUP_ID,
    AccessRightsDict,
    Group,
    GroupID,
    GroupMember,
    GroupsByTypeTuple,
    StandardGroupCreate,
    StandardGroupUpdate,
)
from ..users import UserID, UserNameID, UserNameSafeID
from ..utils.common_validators import create__check_only_one_is_set__root_validator
from ._base import InputSchema, OutputSchema, OutputSchemaWithoutCamelCase

S = TypeVar("S", bound=BaseModel)


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


class GroupGetBase(OutputSchema):
    gid: Annotated[GroupID, Field(description="the group's unique ID")]
    label: Annotated[str, Field(description="the group's display name")]
    description: str
    thumbnail: Annotated[
        AnyUrl | None, Field(description="a link to the group's thumbnail")
    ] = None

    @field_validator("thumbnail", mode="before")
    @classmethod
    def _sanitize_thumbnail_input(cls, v):
        if v:
            # Enforces null if thumbnail is not valid URL or empty
            with suppress(ValidationError):
                return TypeAdapter(AnyHttpUrl).validate_python(v)
        return None

    @classmethod
    def dump_basic_group_data(cls, group: Group) -> dict:
        """Helper function to extract common group data for schema conversion"""
        return remap_keys(
            group.model_dump(
                include={
                    "gid",
                    "name",
                    "description",
                    "thumbnail",
                },
                exclude={
                    "inclusion_rules",  # deprecated
                },
                exclude_unset=True,
                by_alias=False,
            ),
            rename={
                "name": "label",
            },
        )


class GroupGet(GroupGetBase):
    access_rights: Annotated[GroupAccessRights, Field(alias="accessRights")]

    inclusion_rules: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
            alias="inclusionRules",
            deprecated=True,
        ),
    ] = DEFAULT_FACTORY

    @classmethod
    def from_domain_model(cls, group: Group, access_rights: AccessRightsDict) -> Self:
        # Adapts these domain models into this schema
        return cls.model_validate(
            {
                **cls.dump_basic_group_data(group),
                "access_rights": access_rights,
            }
        )

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
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
                        "gid": "1",
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

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)


class GroupCreate(InputSchema):
    label: NameSafeStr
    description: DescriptionSafeStr
    thumbnail: AnyUrl | None = None

    def to_domain_model(self) -> StandardGroupCreate:
        data = remap_keys(
            self.model_dump(
                mode="json",
                # NOTE: intentionally inclusion_rules are not exposed to the REST api
                include={"label", "description", "thumbnail"},
                exclude_unset=True,
            ),
            rename={"label": "name"},
        )
        return StandardGroupCreate(**data)


class GroupUpdate(InputSchema):
    label: NameSafeStr | None = None
    description: DescriptionSafeStr | None = None
    thumbnail: AnyUrl | None = None

    def to_domain_model(self) -> StandardGroupUpdate:
        data = remap_keys(
            self.model_dump(
                mode="json",
                # NOTE: intentionally inclusion_rules are not exposed to the REST api
                include={"label", "description", "thumbnail"},
                exclude_unset=True,
            ),
            rename={"label": "name"},
        )
        return StandardGroupUpdate(**data)


class MyGroupsGet(OutputSchema):
    me: GroupGet
    organizations: list[GroupGet] | None = None
    all: GroupGet
    product: GroupGet | None = None
    support: Annotated[
        GroupGetBase | None,
        Field(
            description="Group ID of the app support team or None if no support is defined for this product"
        ),
    ] = None
    chatbot: Annotated[
        GroupGetBase | None,
        Field(
            description="Group ID of the support chatbot user or None if no chatbot is defined for this product"
        ),
    ] = None

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
                    "gid": EVERYONE_GROUP_ID,
                    "label": "All",
                    "description": "Open to all users",
                    "accessRights": {"read": True, "write": False, "delete": False},
                },
                "support": {
                    "gid": "2",
                    "label": "Support Team",
                    "description": "The support team of the application",
                    "thumbnail": "https://placekitten.com/15/15",
                },
                "chatbot": {
                    "gid": "6",
                    "label": "Chatbot User",
                    "description": "The chatbot user of the application",
                    "thumbnail": "https://placekitten.com/15/15",
                },
            }
        }
    )

    @classmethod
    def from_domain_model(
        cls,
        groups_by_type: GroupsByTypeTuple,
        my_product_group: tuple[Group, AccessRightsDict] | None,
        product_support_group: Group | None,
        product_chatbot_primary_group: Group | None,
    ) -> Self:
        assert groups_by_type.primary  # nosec
        assert groups_by_type.everyone  # nosec

        return cls(
            me=GroupGet.from_domain_model(*groups_by_type.primary),
            organizations=[
                GroupGet.from_domain_model(*gi) for gi in groups_by_type.standard
            ],
            all=GroupGet.from_domain_model(*groups_by_type.everyone),
            product=(
                GroupGet.from_domain_model(*my_product_group)
                if my_product_group
                else None
            ),
            support=(
                GroupGetBase.model_validate(
                    GroupGetBase.dump_basic_group_data(product_support_group)
                )
                if product_support_group
                else None
            ),
            chatbot=(
                GroupGetBase.model_validate(
                    GroupGetBase.dump_basic_group_data(product_chatbot_primary_group)
                )
                if product_chatbot_primary_group
                else None
            ),
        )


class GroupUserGet(OutputSchemaWithoutCamelCase):

    id: Annotated[UserID | None, Field(description="the user's id")] = None
    user_name: Annotated[
        UserNameID | None, Field(alias="userName", description="None if private")
    ] = None
    gid: Annotated[
        GroupID | None,
        Field(description="the user primary gid"),
    ] = None

    login: Annotated[
        LowerCaseEmailStr | None,
        Field(description="the user's email or None if private"),
    ] = None
    first_name: Annotated[str | None, Field(description="None if private")] = None
    last_name: Annotated[str | None, Field(description="None if private")] = None
    gravatar_id: Annotated[
        str | None, Field(description="the user gravatar id hash", deprecated=True)
    ] = None

    # Access Rights
    access_rights: Annotated[
        GroupAccessRights | None,
        Field(
            alias="accessRights",
            description="If group is standard, these are these are the access rights of the user to it."
            "None if primary group.",
        ),
    ] = None

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
            },
            "examples": [
                # unique member on a primary group with two different primacy settings
                {
                    "id": "16",
                    "userName": "mrprivate",
                    "gid": "55",
                },
                # very private user
                {
                    "id": "6",
                    "gid": "55",
                },
                {
                    "id": "56",
                    "userName": "mrpublic",
                    "login": "mrpublic@email.me",
                    "first_name": "Mr",
                    "last_name": "Public",
                    "gid": "42",
                },
            ],
        },
    )

    @classmethod
    def from_domain_model(cls, user: GroupMember) -> Self:
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
    user_name: Annotated[UserNameSafeID | None, Field(alias="userName")] = None
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
