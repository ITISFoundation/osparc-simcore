from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


from ..domain.groups import Groups



class ProfileCommon(BaseModel):
    first_name: Optional[str] = Field(None, example="James")
    last_name: Optional[str] = Field(None, example="Maxwell")


class ProfileUpdate(ProfileCommon):
    pass


# from simcore_postgres_database.models.users import UserRole
class UserRoleEnum(str, Enum):
    # TODO: build from UserRole! or assert Role == UserRole
    ANONYMOUS = "ANONYMOUS"
    GUEST = "GUEST"
    USER = "USER"
    TESTER = "TESTER"


class Profile(ProfileCommon):
    login: EmailStr
    role: UserRoleEnum
    groups: Optional[Groups] = None
    gravatar_id: Optional[str] = None

    class Config:
        schema_extra = {}
