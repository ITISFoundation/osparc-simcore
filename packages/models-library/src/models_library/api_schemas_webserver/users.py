import re
from datetime import date
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from common_library.users_enums import UserStatus
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from ..basic_types import IDStr
from ..emails import LowerCaseEmailStr
from ..products import ProductName
from ..users import FirstNameStr, LastNameStr, UserID
from ._base import InputSchema, OutputSchema
from .groups import MyGroupsGet
from .users_preferences import AggregatedPreferences


#
# TOKENS resource
#
class ThirdPartyToken(BaseModel):
    """
    Tokens used to access third-party services connected to osparc (e.g. pennsieve, scicrunch, etc)
    """

    service: str = Field(
        ..., description="uniquely identifies the service where this token is used"
    )
    token_key: UUID = Field(..., description="basic token key")
    token_secret: UUID | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "github-api-v1",
                "token_key": "5f21abf5-c596-47b7-bfd1-c0e436ef1107",
            }
        }
    )


class TokenCreate(ThirdPartyToken):
    ...


#
# Permissions
#
class Permission(BaseModel):
    name: str
    allowed: bool


class PermissionGet(Permission, OutputSchema):
    ...


#
# My Profile
#


class MyProfilePrivacyGet(OutputSchema):
    hide_fullname: bool
    hide_email: bool


class MyProfilePrivacyPatch(InputSchema):
    hide_fullname: bool | None = None
    hide_email: bool | None = None


class MyProfileGet(BaseModel):
    # WARNING: do not use InputSchema until front-end is updated!
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
# User
#


class SearchQueryParams(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=200,
        description="complete or glob pattern for an email",
    )


class UserGet(OutputSchema):
    first_name: str | None
    last_name: str | None
    email: LowerCaseEmailStr
    institution: str | None
    phone: str | None
    address: str | None
    city: str | None
    state: str | None = Field(description="State, province, canton, ...")
    postal_code: str | None
    country: str | None
    extras: dict[str, Any] = Field(
        default_factory=dict,
        description="Keeps extra information provided in the request form",
    )

    # authorization
    invited_by: str | None = Field(default=None)

    # user status
    registered: bool
    status: UserStatus | None
    products: list[ProductName] | None = Field(
        default=None,
        description="List of products this users is included or None if fields is unset",
    )

    @field_validator("status")
    @classmethod
    def _consistency_check(cls, v, info: ValidationInfo):
        registered = info.data["registered"]
        status = v
        if not registered and status is not None:
            msg = f"{registered=} and {status=} is not allowed"
            raise ValueError(msg)
        return v
