from contextlib import suppress
from typing import Any, ClassVar

from pydantic import AnyUrl, BaseModel, Field, ValidationError, parse_obj_as, validator

from ..emails import LowerCaseEmailStr

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


class GroupUserGet(BaseModel):
    id: str | None = Field(None, description="the user id")
    login: LowerCaseEmailStr | None = Field(None, description="the user login email")
    first_name: str | None = Field(None, description="the user first name")
    last_name: str | None = Field(None, description="the user last name")
    gravatar_id: str | None = Field(None, description="the user gravatar id hash")
    gid: str | None = Field(None, description="the user primary gid")
    access_rights: GroupAccessRights = Field(..., alias="accessRights")

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "id": "1",
                "login": "mr.smith@matrix.com",
                "first_name": "Mr",
                "last_name": "Smith",
                "gravatar_id": "a1af5c6ecc38e81f29695f01d6ceb540",
                "gid": "3",
                "accessRights": {
                    "read": True,
                    "write": False,
                    "delete": False,
                },
            }
        }
