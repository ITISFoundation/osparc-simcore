import re
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Literal, Self

import annotated_types
from common_library.basic_types import DEFAULT_FACTORY
from common_library.dict_tools import remap_keys
from common_library.users_enums import AccountRequestStatus, UserStatus
from models_library.groups import AccessRightsDict
from models_library.rest_filters import Filters
from models_library.rest_pagination import PageQueryParameters
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.config import JsonDict

from ..basic_types import IDStr
from ..emails import LowerCaseEmailStr
from ..groups import AccessRightsDict, Group, GroupID, GroupsByTypeTuple, PrimaryGroupID
from ..products import ProductName
from ..rest_base import RequestParameters
from ..string_types import (
    GlobPatternSafeStr,
    SearchPatternSafeStr,
    validate_input_xss_safety,
)
from ..users import (
    FirstNameStr,
    LastNameStr,
    MyProfile,
    UserID,
    UserNameID,
    UserNameSafeID,
    UserPermission,
    UserThirdPartyToken,
)
from ._base import (
    InputSchema,
    InputSchemaWithoutCamelCase,
    OutputSchema,
    OutputSchemaWithoutCamelCase,
)
from .groups import MyGroupsGet
from .products import TrialAccountAnnotated, WelcomeCreditsAnnotated
from .users_preferences import AggregatedPreferences

#
# MY PROFILE
#


class MyProfilePrivacyGet(OutputSchema):
    hide_username: bool
    hide_fullname: bool
    hide_email: bool


class MyProfilePrivacyPatch(InputSchema):
    hide_username: bool | None = None
    hide_fullname: bool | None = None
    hide_email: bool | None = None


class MyProfileAddressGet(OutputSchema):
    """Details provided upon registration and used e.g. for invoicing"""

    institution: str | None
    address: str | None
    city: str | None
    state: Annotated[str | None, Field(description="State, province, canton, ...")]
    postal_code: str | None
    country: str | None


class MyProfileRestGet(OutputSchemaWithoutCamelCase):
    id: UserID
    user_name: Annotated[
        IDStr, Field(description="Unique username identifier", alias="userName")
    ]
    first_name: FirstNameStr | None = None
    last_name: LastNameStr | None = None
    login: LowerCaseEmailStr
    phone: str | None = None

    role: Literal[
        "ANONYMOUS",
        "GUEST",
        "USER",
        "TESTER",
        "PRODUCT_OWNER",
        "ADMIN",
    ]
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
    contact: MyProfileAddressGet | None = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "id": 42,
                        "login": "bla@foo.com",
                        "userName": "bla42",
                        "role": "admin",  # pre
                        "expirationDate": "2022-09-14",  # optional
                        "preferences": {},
                        "privacy": {
                            "hide_username": 0,
                            "hide_fullname": 0,
                            "hide_email": 1,
                        },
                    },
                    {
                        "id": 1,
                        "login": "minimal@user.com",
                        "userName": "minuser",
                        "role": "USER",
                        "preferences": {},
                        "privacy": {
                            "hide_username": False,
                            "hide_fullname": False,
                            "hide_email": False,
                        },
                        "provided": {
                            "address": "123 Main St",
                            "city": "Sampleville",
                            "state": "CA",
                            "postal_code": "12345",
                            "country": "Wonderland",
                        },
                    },
                ]
            }
        )

    model_config = ConfigDict(
        # NOTE: old models have an hybrid between snake and camel cases!
        # Should be unified at some point
        populate_by_name=True,
        json_schema_extra=_update_json_schema_extra,
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
    def from_domain_model(
        cls,
        my_profile: MyProfile,
        my_groups_by_type: GroupsByTypeTuple,
        my_product_group: tuple[Group, AccessRightsDict] | None,
        my_preferences: AggregatedPreferences,
        my_support_group: Group | None,
        profile_contact: MyProfileAddressGet | None = None,
    ) -> Self:
        profile_data = remap_keys(
            my_profile.model_dump(
                include={
                    "id",
                    "user_name",
                    "first_name",
                    "last_name",
                    "email",
                    "role",
                    "phone",
                    "privacy",
                    "expiration_date",
                },
                exclude_unset=True,
            ),
            rename={"email": "login"},
        )
        return cls(
            **profile_data,
            groups=MyGroupsGet.from_domain_model(
                my_groups_by_type, my_product_group, my_support_group
            ),
            preferences=my_preferences,
            contact=profile_contact,
        )


FirstNameSafeStr = Annotated[
    FirstNameStr,
    AfterValidator(validate_input_xss_safety),
]

LastNameSafeStr = Annotated[
    LastNameStr,
    AfterValidator(validate_input_xss_safety),
]


class MyProfileRestPatch(InputSchemaWithoutCamelCase):
    first_name: FirstNameSafeStr | None = None
    last_name: LastNameSafeStr | None = None
    user_name: Annotated[UserNameSafeID | None, Field(alias="userName")] = None
    # NOTE: phone is updated via a dedicated endpoint!

    privacy: MyProfilePrivacyPatch | None = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update({"examples": [{"first_name": "Pedro", "last_name": "Crespo"}]})

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)

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
            msg = f"Username '{value}' cannot end with a special character."
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


class UsersGetParams(RequestParameters):
    user_id: UserID


class UsersSearch(InputSchema):
    match_: Annotated[
        SearchPatternSafeStr,
        Field(
            description="Search string to match with usernames and public profiles (e.g. emails, first/last name)",
            alias="match",
        ),
    ]
    limit: Annotated[int, annotated_types.Interval(ge=1, le=50)] = 10


class UserGet(OutputSchema):
    # Public profile of a user subject to its privacy settings
    user_id: UserID
    group_id: GroupID
    user_name: UserNameID | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None

    @classmethod
    def from_domain_model(cls, data):
        return cls.model_validate(data, from_attributes=True)


class UsersForAdminListFilter(Filters):
    # 1. account_request_status: PENDING, REJECTED, APPROVED
    # 2. If APPROVED AND user uses the invitation link, then when user is registered,
    #  it can be in any of these statuses:
    #     CONFIRMATION_PENDING, ACTIVE, EXPIRED, BANNED, DELETED
    #
    review_status: Literal["PENDING", "REVIEWED"] | None = None

    model_config = ConfigDict(extra="forbid")


class UsersAccountListQueryParams(UsersForAdminListFilter, PageQueryParameters): ...


class _InvitationDetails(InputSchema):
    trial_account_days: TrialAccountAnnotated = None
    extra_credits_in_usd: WelcomeCreditsAnnotated = None


class UserAccountApprove(InputSchema):
    email: EmailStr
    invitation: _InvitationDetails | None = None


class UserAccountReject(InputSchema):
    email: EmailStr


class UserAccountSearchQueryParams(RequestParameters):
    email: Annotated[
        GlobPatternSafeStr | None,
        Field(
            description="complete or glob pattern for an email",
        ),
    ] = None
    primary_group_id: Annotated[
        GroupID | None,
        Field(
            description="Filter by primary group ID",
        ),
    ] = None
    user_name: Annotated[
        GlobPatternSafeStr | None,
        Field(
            description="complete or glob pattern for a username",
        ),
    ] = None

    @model_validator(mode="after")
    def _validate_at_least_one_filter(self) -> Self:
        field_names = list(self.__class__.model_fields)
        if not any(getattr(self, field_name, None) for field_name in field_names):
            msg = f"At least one filter {field_names} must be provided"
            raise ValueError(msg)
        return self


class UserAccountGet(OutputSchema):
    # ONLY for admins
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

    # pre-registration NOTE: that some users have no pre-registartion and therefore all options here can be none
    pre_registration_id: int | None
    pre_registration_created: datetime | None
    invited_by: UserNameID | None = None
    account_request_status: AccountRequestStatus | None
    account_request_reviewed_by: UserNameID | None = None
    account_request_reviewed_at: datetime | None = None

    # user status
    registered: bool
    status: UserStatus | None = None
    products: Annotated[
        list[ProductName] | None,
        Field(
            description="List of products this users is included or None if fields is unset",
        ),
    ] = None

    # user (if an account was created)
    user_id: Annotated[
        UserID | None,
        Field(description="Unique identifier of the user if an account was created"),
    ] = None
    user_name: Annotated[
        UserNameID | None,
        Field(description="Username of the user if an account was created"),
    ] = None
    user_primary_group_id: Annotated[
        PrimaryGroupID | None,
        Field(
            description="Primary group ID of the user if an account was created",
            alias="groupId",
            # SEE https://github.com/ITISFoundation/osparc-simcore/pull/8358#issuecomment-3279491740
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


class TokenPathParams(BaseModel):
    service: str


class MyTokenCreate(InputSchemaWithoutCamelCase):
    service: Annotated[
        IDStr,
        Field(description="uniquely identifies the service where this token is used"),
    ]
    token_key: IDStr
    token_secret: IDStr

    def to_domain_model(self) -> UserThirdPartyToken:
        return UserThirdPartyToken(
            service=self.service,
            token_key=self.token_key,
            token_secret=self.token_secret,
        )


class MyTokenGet(OutputSchemaWithoutCamelCase):
    service: IDStr
    token_key: IDStr
    token_secret: Annotated[
        IDStr | None, Field(deprecated=True, description="Will be removed")
    ] = None

    @classmethod
    def from_domain_model(cls, token: UserThirdPartyToken) -> Self:
        return cls(
            service=token.service,  # type: ignore[arg-type]
            token_key=token.token_key,  # type: ignore[arg-type]
            token_secret=None,
        )


#
# PERMISSIONS
#


class MyPermissionGet(OutputSchema):
    name: str
    allowed: bool

    @classmethod
    def from_domain_model(cls, permission: UserPermission) -> Self:
        return cls(name=permission.name, allowed=permission.allowed)


class MyFunctionPermissionsGet(OutputSchema):
    read_functions: bool
    write_functions: bool
