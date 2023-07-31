from contextlib import suppress
from typing import Any, ClassVar

from models_library.emails import LowerCaseEmailStr
from pydantic import AnyUrl, BaseModel, Field, ValidationError, parse_obj_as, validator

from ._utils import convert_groups_db_to_schema

#
# GROUPS MODELS defined in OPENAPI specs
#


class GroupAccessRights(BaseModel):
    """
    defines acesss rights for the user
    """

    read: bool
    write: bool
    delete: bool

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"read": True, "write": False, "delete": False},
                {"read": True, "write": True, "delete": False},
                {"read": True, "write": True, "delete": True},
            ]
        }


class UsersGroup(BaseModel):
    gid: int = Field(..., description="the group ID")
    label: str = Field(..., description="the group name")
    description: str = Field(..., description="the group description")
    thumbnail: AnyUrl | None = Field(
        default=None, description="url to the group thumbnail"
    )
    access_rights: GroupAccessRights = Field(..., alias="accessRights")
    inclusion_rules: dict[str, str] = Field(
        default_factory=dict,
        description="Maps user's column and regular expression",
        alias="inclusionRules",
    )

    @validator("thumbnail", pre=True)
    @classmethod
    def sanitize_legacy_data(cls, v):
        if v:
            # Enforces null if thumbnail is not valid URL or empty
            with suppress(ValidationError):
                return parse_obj_as(AnyUrl, v)
        return None

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "gid": "27",
                    "label": "A user",
                    "description": "A very special user",
                    "thumbnail": "https://placekitten.com/10/10",
                    "accessRights": {"read": True, "write": False, "delete": False},
                },
                {
                    "gid": 1,
                    "label": "ITIS Foundation",
                    "description": "The Foundation for Research on Information Technologies in Society",
                    "accessRights": {"read": True, "write": False, "delete": False},
                },
                {
                    "gid": "0",
                    "label": "All",
                    "description": "Open to all users",
                    "accessRights": {"read": True, "write": True, "delete": True},
                },
                {
                    "gid": 5,
                    "label": "SPARCi",
                    "description": "Stimulating Peripheral Activity to Relieve Conditions",
                    "thumbnail": "https://placekitten.com/15/15",
                    "inclusionRules": {"email": r"@(sparc)+\.(io|com|us)$"},
                    "accessRights": {"read": True, "write": True, "delete": True},
                },
            ]
        }


class AllUsersGroups(BaseModel):
    me: UsersGroup | None = None
    organizations: list[UsersGroup] | None = None
    all: UsersGroup | None = None
    product: UsersGroup | None = None

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "me": {
                    "gid": "27",
                    "label": "A user",
                    "description": "A very special user",
                    "accessRights": {"read": True, "write": True, "delete": True},
                },
                "organizations": [
                    {
                        "gid": "15",
                        "label": "ITIS Foundation",
                        "description": "The Foundation for Research on Information Technologies in Society",
                        "accessRights": {
                            "read": True,
                            "write": False,
                            "delete": False,
                        },
                    },
                    {
                        "gid": "16",
                        "label": "Blue Fundation",
                        "description": "Some foundation",
                        "accessRights": {
                            "read": True,
                            "write": False,
                            "delete": False,
                        },
                    },
                ],
                "all": {
                    "gid": "0",
                    "label": "All",
                    "description": "Open to all users",
                    "accessRights": {"read": True, "write": False, "delete": False},
                },
            }
        }


class GroupUser(GroupAccessRights):
    first_name: str | None = Field(None, description="the user first name")
    last_name: str | None = Field(None, description="the user last name")
    login: LowerCaseEmailStr | None = Field(None, description="the user login email")
    gravatar_id: str | None = Field(None, description="the user gravatar id hash")
    id: str | None = Field(None, description="the user id")
    gid: str | None = Field(None, description="the user primary gid")

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "first_name": "Mr",
                "last_name": "Smith",
                "login": "mr.smith@matrix.com",
                "gravatar_id": "a1af5c6ecc38e81f29695f01d6ceb540",
                "id": "1",
                "gid": "3",
                "read": True,
                "write": False,
                "delete": False,
            }
        }


# Avoids pycln to remove import
assert convert_groups_db_to_schema  # nosec

__all__: tuple[str, ...] = ("convert_groups_db_to_schema",)
