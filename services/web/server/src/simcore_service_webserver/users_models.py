from datetime import date
from typing import Optional
from uuid import UUID

from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, EmailStr, Field
from servicelib.json_serialization import json_dumps
from simcore_postgres_database.models.users import UserRole

from .groups_models import AllUsersGroups

#
# TOKENS resource
#


class Token(BaseModel):
    """
    api keys for third party services
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
    login: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    groups: Optional[AllUsersGroups] = None
    gravatar_id: Optional[str] = None
    expiration_date: Optional[date] = Field(
        default=None,
        description="If user has a trial account, it sets the expiration date, otherwise None",
    )

    class Config:
        alias_generator = snake_to_camel
        allow_population_by_field_name = True
        json_dumps = json_dumps

        schema_extra = {
            "example": {
                "login": "bla@foo.com",
                "role": "ADMIN",
                "gravatar_id": "205e460b479e2e5b48aec07710c08d50",
            }
        }
