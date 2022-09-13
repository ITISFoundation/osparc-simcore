from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from .groups_models import AllUsersGroups

#
# TOKENS
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
# USERS
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


class ProfileInput(_ProfileCommon):
    pass


class ProfileOutput(_ProfileCommon):
    login: Optional[EmailStr] = None
    role: Optional[str] = None
    groups: Optional[AllUsersGroups] = None
    gravatar_id: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "login": "pcrespov@foo.com",
                "role": "Admin",
                "gravatar_id": "205e460b479e2e5b48aec07710c08d50",
            }
        }
