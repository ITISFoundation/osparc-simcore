import datetime
from typing import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    Annotated,
    TypeAlias,
    TypedDict,
)

from common_library.users_enums import UserRole
from models_library.string_types import validate_input_xss_safety
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    StringConstraints,
)
from pydantic.config import JsonDict

from .emails import LowerCaseEmailStr

UserID: TypeAlias = PositiveInt
UserNameID: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=4, max_length=100)
]
UserNameSafeID: TypeAlias = Annotated[
    UserNameID, AfterValidator(validate_input_xss_safety)
]


FirstNameStr: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=255)
]

LastNameStr: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=255)
]


class PrivacyDict(TypedDict):
    hide_username: bool
    hide_fullname: bool
    hide_email: bool


class MyProfile(BaseModel):
    id: UserID
    user_name: UserNameID
    first_name: str | None
    last_name: str | None
    email: LowerCaseEmailStr
    role: UserRole
    privacy: PrivacyDict
    phone: str | None
    expiration_date: datetime.date | None = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "example": {
                    "id": 1,
                    "email": "PtN5Ab0uv@guest-at-osparc.io",
                    "user_name": "PtN5Ab0uv",
                    "first_name": "PtN5Ab0uv",
                    "last_name": "",
                    "phone": None,
                    "role": "GUEST",
                    "privacy": {
                        "hide_email": True,
                        "hide_fullname": False,
                        "hide_username": False,
                    },
                }
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)


class UserBillingDetails(BaseModel):
    first_name: str | None
    last_name: str | None
    institution: str | None
    address: str | None
    city: str | None
    state: Annotated[str | None, Field(description="State, province, canton, ...")]
    country: Annotated[
        str,
        Field(description="Billing country (with standardize name) required for taxes"),
    ]
    postal_code: str | None
    phone: str | None

    model_config = ConfigDict(from_attributes=True)


#
# THIRD-PARTY TOKENS
#


class UserThirdPartyToken(BaseModel):
    """
    Tokens used to access third-party services connected to osparc (e.g. pennsieve, scicrunch, etc)
    """

    service: str
    token_key: str
    token_secret: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "github-api-v1",
                "token_key": "5f21abf5-c596-47b7-bfd1-c0e436ef1107",
            }
        }
    )


#
# PERMISSIONS
#


class UserPermission(BaseModel):
    name: str
    allowed: bool
