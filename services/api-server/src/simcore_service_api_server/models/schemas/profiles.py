from enum import auto

from models_library.emails import LowerCaseEmailStr
from models_library.users import FirstNameStr, LastNameStr, UserID
from models_library.utils.enums import StrAutoEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.groups import Groups


class ProfileCommon(BaseModel):
    first_name: FirstNameStr | None = Field(None, examples=["James"])
    last_name: LastNameStr | None = Field(None, examples=["Maxwell"])


class ProfileUpdate(ProfileCommon):
    ...


class UserRoleEnum(StrAutoEnum):
    # NOTE: this is in sync with simcore_postgres_database.models.users.UserRole via testing
    ANONYMOUS = auto()
    GUEST = auto()
    USER = auto()
    TESTER = auto()
    PRODUCT_OWNER = auto()
    ADMIN = auto()


class Profile(ProfileCommon):
    id_: UserID = Field(alias="id")
    login: LowerCaseEmailStr
    role: UserRoleEnum
    groups: Groups | None = None
    gravatar_id: str | None = Field(
        None,
        description="md5 hash value of email to retrieve an avatar image from https://www.gravatar.com",
        max_length=40,
    )

    @field_validator("role", mode="before")
    @classmethod
    def enforce_role_upper(cls, v):
        if v:
            return v.upper()
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "20",
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
    )
