from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from models_library.api_schemas_webserver._base import OutputSchema
from models_library.api_schemas_webserver.groups import MyGroupsGet
from models_library.api_schemas_webserver.users_preferences import AggregatedPreferences
from models_library.basic_types import IDStr
from models_library.emails import LowerCaseEmailStr
from models_library.users import FirstNameStr, LastNameStr, UserID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from simcore_postgres_database.models.users import UserRole

from ._models import ProfilePrivacyGet, ProfilePrivacyUpdate


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
# PROFILE resource
#


class ProfileGet(BaseModel):
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

    privacy: ProfilePrivacyGet
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
                    "userName": "bla123",
                    "role": UserRole.ADMIN.value,
                    "expirationDate": "2022-09-14",
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
        if isinstance(v, UserRole):
            return v.name.upper()
        return v


class ProfileUpdate(BaseModel):
    first_name: FirstNameStr | None = None
    last_name: LastNameStr | None = None

    privacy: ProfilePrivacyUpdate | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Pedro",
                "last_name": "Crespo",
            }
        }
    )


#
# Permissions
#
class Permission(BaseModel):
    name: str
    allowed: bool


class PermissionGet(Permission, OutputSchema):
    ...
