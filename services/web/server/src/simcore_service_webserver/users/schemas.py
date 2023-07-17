from datetime import date
from typing import Any, Literal, Mapping
from uuid import UUID

from models_library.api_schemas_webserver._base import OutputSchema
from models_library.basic_types import IdInt
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, Field, validator
from servicelib.json_serialization import json_dumps
from simcore_postgres_database.models.users import UserRole

from ..groups.schemas import AllUsersGroups
from ..utils import gravatar_hash


#
# TOKENS resource
#
class Token(BaseModel):
    """
    Tokens used to access third-party services connected to osparc (e.g. pennsieve, scicrunch, etc)
    """

    service: str = Field(
        ..., description="uniquely identifies the service where this token is used"
    )
    token_key: UUID = Field(..., description="basic token key")
    token_secret: UUID | None = None

    class Config:
        schema_extra = {
            "example": {
                "service": "github-api-v1",
                "token_key": "5f21abf5-c596-47b7-bfd1-c0e436ef1107",
            }
        }


class TokenID(BaseModel):
    __root__: str = Field(..., description="toke identifier")


class TokenCreate(Token):
    ...


#
# PROFILE resource
#


class _ProfileCommon(BaseModel):
    first_name: str | None = None
    last_name: str | None = None

    class Config:
        schema_extra = {
            "example": {
                "first_name": "Pedro",
                "last_name": "Crespo",
            }
        }


class ProfileUpdate(_ProfileCommon):
    pass


class ProfileGet(_ProfileCommon):
    id: IdInt
    login: LowerCaseEmailStr
    role: Literal["Anonymous", "Guest", "User", "Tester", "Admin"]
    groups: AllUsersGroups | None = None
    gravatar_id: str | None = None
    expiration_date: date | None = Field(
        default=None,
        description="If user has a trial account, it sets the expiration date, otherwise None",
        alias="expirationDate",
    )

    class Config:
        # NOTE: old models have an hybrid between snake and camel cases!
        # Should be unified at some point
        allow_population_by_field_name = True
        json_dumps = json_dumps

        schema_extra = {
            "examples": [
                {
                    "id": 1,
                    "login": "bla@foo.com",
                    "role": "Admin",
                    "gravatar_id": "205e460b479e2e5b48aec07710c08d50",
                },
                {
                    "id": 42,
                    "login": "bla@foo.com",
                    "role": UserRole.ADMIN,
                    "expirationDate": "2022-09-14",
                },
            ]
        }

    @validator("role", pre=True)
    @classmethod
    def to_capitalize(cls, v):
        if isinstance(v, str):
            return v.capitalize()
        if isinstance(v, UserRole):
            return v.name.capitalize()
        return v


#
# helpers
#


def convert_user_db_to_schema(
    row: Mapping[str, Any], prefix: Literal["users_", ""] = ""
) -> dict[str, Any]:
    # NOTE: this type of functions will be replaced by pydantic.
    assert prefix is not None  # nosec
    parts = row[f"{prefix}name"].split(".") + [""]
    data = {
        "id": row[f"{prefix}id"],
        "login": row[f"{prefix}email"],
        "first_name": parts[0],
        "last_name": parts[1],
        "role": row[f"{prefix}role"].name.capitalize(),
        "gravatar_id": gravatar_hash(row[f"{prefix}email"]),
    }

    if expires_at := row[f"{prefix}expires_at"]:
        data["expires_at"] = expires_at
    return data


#
# Permissions
#
class Permission(BaseModel):
    name: str
    allowed: bool


class PermissionGet(Permission, OutputSchema):
    ...
