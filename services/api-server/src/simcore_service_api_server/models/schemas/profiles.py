from enum import Enum
from typing import Optional

from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, Field

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
    ADMIN = "ADMIN"


class Profile(ProfileCommon):
    login: LowerCaseEmailStr
    role: UserRoleEnum
    groups: Optional[Groups] = None
    gravatar_id: Optional[str] = Field(
        None,
        description="md5 hash value of email to retrieve an avatar image from https://www.gravatar.com",
        max_length=40,
    )

    class Config:
        schema_extra = {
            "example": {
                "first_name": "James",
                "last_name": "Maxwell",
                "login": "james-maxwell@itis.swiss",
                "role": "USER",
                "groups": {
                    "me": {
                        "gid": "123",
                        "label": "maxy",
                        "description": "primary group",
                    },
                    "organizations": [],
                    "all": {
                        "gid": "1",
                        "label": "Everyone",
                        "description": "all users",
                    },
                },
                "gravatar_id": "9a8930a5b20d7048e37740bac5c1ca4f",
            }
        }
