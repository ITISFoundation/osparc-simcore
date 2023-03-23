from datetime import date
from typing import Literal, Optional
from uuid import UUID

from models_library.basic_types import IdInt
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, Field, validator
from servicelib.json_serialization import json_dumps
from simcore_postgres_database.models.users import UserRole

from .groups_models import AllUsersGroups

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
    token_secret: Optional[UUID] = None

    class Config:
        schema_extra = {
            "example": {
                "service": "github-api-v1",
                "token_key": "5f21abf5-c596-47b7-bfd1-c0e436ef1107",
            }
        }


class TokenID(BaseModel):
    __root__: str = Field(..., description="toke identifier")


#
# PROFILE resource
#


class _ProfileCommon(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None

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
    groups: Optional[AllUsersGroups] = None
    gravatar_id: Optional[str] = None
    expiration_date: Optional[date] = Field(
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
