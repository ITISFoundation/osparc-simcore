from datetime import date
from typing import Literal
from uuid import UUID

from models_library.api_schemas_webserver._base import OutputSchema
from models_library.api_schemas_webserver.groups import MyGroupsGet
from models_library.api_schemas_webserver.users_preferences import AggregatedPreferences
from models_library.emails import LowerCaseEmailStr
from models_library.users import FirstNameStr, LastNameStr, UserID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from simcore_postgres_database.models.users import UserRole

from ..utils import gravatar_hash


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


class ProfileUpdate(BaseModel):
    first_name: FirstNameStr | None = None
    last_name: LastNameStr | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Pedro",
                "last_name": "Crespo",
            }
        }
    )


class ProfileGet(BaseModel):
    id: UserID
    first_name: FirstNameStr | None = None
    last_name: LastNameStr | None = None
    login: LowerCaseEmailStr
    role: Literal["ANONYMOUS", "GUEST", "USER", "TESTER", "PRODUCT_OWNER", "ADMIN"]
    groups: MyGroupsGet | None = None
    gravatar_id: str | None = None
    expiration_date: date | None = Field(
        default=None,
        description="If user has a trial account, it sets the expiration date, otherwise None",
        alias="expirationDate",
    )
    preferences: AggregatedPreferences

    model_config = ConfigDict(
        # NOTE: old models have an hybrid between snake and camel cases!
        # Should be unified at some point
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "login": "bla@foo.com",
                    "role": "Admin",
                    "gravatar_id": "205e460b479e2e5b48aec07710c08d50",
                    "preferences": {},
                },
                {
                    "id": 42,
                    "login": "bla@foo.com",
                    "role": UserRole.ADMIN.value,
                    "expirationDate": "2022-09-14",
                    "preferences": {},
                },
            ]
        },
    )

    @model_validator(mode="before")
    @classmethod
    def _auto_generate_gravatar(cls, values):
        gravatar_id = values.get("gravatar_id")
        email = values.get("login")
        if not gravatar_id and email:
            values["gravatar_id"] = gravatar_hash(email)
        return values

    @field_validator("role", mode="before")
    @classmethod
    def _to_upper_string(cls, v):
        if isinstance(v, str):
            return v.upper()
        if isinstance(v, UserRole):
            return v.name.upper()
        return v


#
# Permissions
#
class Permission(BaseModel):
    name: str
    allowed: bool


class PermissionGet(Permission, OutputSchema):
    ...
