import re
from datetime import date
from enum import Enum
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from common_library.basic_types import DEFAULT_FACTORY
from common_library.users_enums import UserStatus
from models_library.groups import AccessRightsDict
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from ..basic_types import IDStr
from ..emails import LowerCaseEmailStr
from ..groups import AccessRightsDict, Group, GroupsByTypeTuple
from ..products import ProductName
from ..users import (
    FirstNameStr,
    LastNameStr,
    MyProfile,
    UserID,
    UserPermission,
    UserThirdPartyToken,
)
from ._base import (
    InputSchema,
    InputSchemaWithoutCamelCase,
    OutputSchema,
    OutputSchemaWithoutCamelCase,
    copy_dict,
)
from .groups import MyGroupsGet
from .users_preferences import AggregatedPreferences

#
# MY PROFILE
#


class MyProfilePrivacyGet(OutputSchema):
    hide_fullname: bool
    hide_email: bool


class MyProfilePrivacyPatch(InputSchema):
    hide_fullname: bool | None = None
    hide_email: bool | None = None


class MyProfileGet(OutputSchemaWithoutCamelCase):
    id: UserID
    user_name: Annotated[
        IDStr, Field(description="Unique username identifier", alias="userName")
    ]
    first_name: FirstNameStr | None = None
    last_name: LastNameStr | None = None
    login: LowerCaseEmailStr

    role: Literal["ANONYMOUS", "GUEST", "USER", "TESTER", "PRODUCT_OWNER", "ADMIN"]
    groups: MyGroupsGet | None = None
    gravatar_id: Annotated[str | None, Field(deprecated=True)] = None

    expiration_date: Annotated[
        date | None,
        Field(
            description="If user has a trial account, it sets the expiration date, otherwise None",
            alias="expirationDate",
        ),
    ] = None

    privacy: MyProfilePrivacyGet
    preferences: AggregatedPreferences

    model_config = ConfigDict(
        # NOTE: old models have an hybrid between snake and camel cases!
        # Should be unified at some point
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 42,
                    "login": "bla@foo.com",
                    "userName": "bla42",
                    "role": "admin",  # pre
                    "expirationDate": "2022-09-14",  # optional
                    "preferences": {},
                    "privacy": {"hide_fullname": 0, "hide_email": 1},
                },
            ]
        },
    )

    @field_validator("role", mode="before")
    @classmethod
    def _to_upper_string(cls, v):
        if isinstance(v, str):
            return v.upper()
        if isinstance(v, Enum):
            return v.name.upper()
        return v

    @classmethod
    def from_model(
        cls,
        my_profile: MyProfile,
        my_groups_by_type: GroupsByTypeTuple,
        my_product_group: tuple[Group, AccessRightsDict],
        my_preferences: AggregatedPreferences,
    ) -> Self:
        data = copy_dict(
            my_profile.model_dump(
                include={
                    "id",
                    "user_name",
                    "first_name",
                    "last_name",
                    "email",
                    "role",
                    "privacy",
                    "expiration_date",
                },
                exclude_unset=True,
            ),
            update_keys={"email": "login"},
        )
        return cls(
            **data,
            groups=MyGroupsGet.from_model(my_groups_by_type, my_product_group),
            preferences=my_preferences,
        )


class MyProfilePatch(BaseModel):
    # WARNING: do not use InputSchema until front-end is updated!
    first_name: FirstNameStr | None = None
    last_name: LastNameStr | None = None
    user_name: Annotated[IDStr | None, Field(alias="userName")] = None

    privacy: MyProfilePrivacyPatch | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Pedro",
                "last_name": "Crespo",
            }
        }
    )

    @field_validator("user_name")
    @classmethod
    def _validate_user_name(cls, value: str):
        # Ensure valid characters (alphanumeric + . _ -)
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9._-]*$", value):
            msg = f"Username '{value}' must start with a letter and can only contain letters, numbers and '_', '.' or '-'."
            raise ValueError(msg)

        # Ensure no consecutive special characters
        if re.search(r"[_.-]{2,}", value):
            msg = f"Username '{value}' cannot contain consecutive special characters like '__'."
            raise ValueError(msg)

        # Ensure it doesn't end with a special character
        if {value[0], value[-1]}.intersection({"_", "-", "."}):
            msg = f"Username '{value}' cannot end or start with a special character."
            raise ValueError(msg)

        # Check reserved words (example list; extend as needed)
        reserved_words = {
            "admin",
            "root",
            "system",
            "null",
            "undefined",
            "support",
            "moderator",
            # NOTE: add here extra via env vars
        }
        if any(w in value.lower() for w in reserved_words):
            msg = f"Username '{value}' cannot be used."
            raise ValueError(msg)

        return value


#
# USER
#


class UsersSearchQueryParams(BaseModel):
    email: Annotated[
        str,
        Field(
            min_length=3,
            max_length=200,
            description="complete or glob pattern for an email",
        ),
    ]


class UserGet(OutputSchema):
    first_name: str | None
    last_name: str | None
    email: LowerCaseEmailStr
    institution: str | None
    phone: str | None
    address: str | None
    city: str | None
    state: Annotated[str | None, Field(description="State, province, canton, ...")]
    postal_code: str | None
    country: str | None
    extras: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            description="Keeps extra information provided in the request form",
        ),
    ] = DEFAULT_FACTORY

    # authorization
    invited_by: str | None = None

    # user status
    registered: bool
    status: UserStatus | None
    products: Annotated[
        list[ProductName] | None,
        Field(
            description="List of products this users is included or None if fields is unset",
        ),
    ] = None

    @field_validator("status")
    @classmethod
    def _consistency_check(cls, v, info: ValidationInfo):
        registered = info.data["registered"]
        status = v
        if not registered and status is not None:
            msg = f"{registered=} and {status=} is not allowed"
            raise ValueError(msg)
        return v


#
# THIRD-PARTY TOKENS
#


class MyTokenCreate(InputSchemaWithoutCamelCase):
    service: Annotated[
        str,
        Field(description="uniquely identifies the service where this token is used"),
    ]
    token_key: UUID
    token_secret: UUID

    def to_model(self) -> UserThirdPartyToken:
        return UserThirdPartyToken(
            service=self.service,
            token_key=self.token_key,
            token_secret=self.token_secret,
        )


class MyTokenGet(OutputSchemaWithoutCamelCase):
    service: str
    token_key: UUID
    token_secret: Annotated[
        UUID | None, Field(deprecated=True, description="Will be removed")
    ] = None

    @classmethod
    def from_model(cls, token: UserThirdPartyToken) -> Self:
        return cls(service=token.service, token_key=token.token_key, token_secret=None)


#
# PERMISSIONS
#


class MyPermissionGet(OutputSchema):
    name: str
    allowed: bool

    @classmethod
    def from_model(cls, permission: UserPermission) -> Self:
        return cls(name=permission.name, allowed=permission.allowed)
