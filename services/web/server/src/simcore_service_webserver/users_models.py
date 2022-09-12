from typing import Any, Optional

from pydantic import AnyUrl, BaseModel, EmailStr, Field

#
# GROUPS
#


class GroupAccessRights(BaseModel):
    """
    defines acesss rights for the user
    """

    read: bool
    write: bool
    delete: bool

    class Config:
        schema_extra = {
            "examples": [
                {"read": True, "write": False, "delete": False},
                {"read": True, "write": True, "delete": False},
                {"read": True, "write": True, "delete": True},
            ]
        }


class UsersGroup(BaseModel):
    gid: str = Field(..., description="the group ID")
    label: str = Field(..., description="the group name")
    description: str = Field(..., description="the group description")
    thumbnail: Optional[AnyUrl] = Field(None, description="url to the group thumbnail")
    access_rights: GroupAccessRights = Field(..., alias="accessRights")

    class Config:
        schema_extra = {
            "examples": [
                {
                    "gid": "27",
                    "label": "A user",
                    "description": "A very special user",
                    "thumbnail": "https://user-images.githubusercontent.com/32800795/61083844-ff48fb00-a42c-11e9-8e63-fa2d709c8baf.png",
                },
                {
                    "gid": "1",
                    "label": "ITIS Foundation",
                    "description": "The Foundation for Research on Information Technologies in Society",
                    "thumbnail": "https://user-images.githubusercontent.com/32800795/61083844-ff48fb00-a42c-11e9-8e63-fa2d709c8baf.png",
                },
                {
                    "gid": "0",
                    "label": "All",
                    "description": "Open to all users",
                    "thumbnail": "https://user-images.githubusercontent.com/32800795/61083844-ff48fb00-a42c-11e9-8e63-fa2d709c8baf.png",
                },
            ]
        }


class UsersGroupEnveloped(BaseModel):
    data: UsersGroup
    error: Optional[Any] = None


class AllUsersGroups(BaseModel):
    me: Optional[UsersGroup] = None
    organizations: Optional[list[UsersGroup]] = None
    all: Optional[UsersGroup] = None


class AllUsersGroupsEnveloped(BaseModel):
    data: AllUsersGroups
    error: Optional[Any] = None


class GroupUser(GroupAccessRights):
    first_name: Optional[str] = Field(None, description="the user first name")
    last_name: Optional[str] = Field(None, description="the user last name")
    login: Optional[EmailStr] = Field(None, description="the user login email")
    gravatar_id: Optional[str] = Field(None, description="the user gravatar id hash")
    id: Optional[str] = Field(None, description="the user id")
    gid: Optional[str] = Field(None, description="the user primary gid")

    class Config:
        schema_extra = {
            "example": {
                "first_name": "Mr",
                "last_name": "Smith",
                "login": "mr.smith@matrix.com",
                "gravatar_id": "a1af5c6ecc38e81f29695f01d6ceb540",
                "id": "1",
                "gid": "3",
            }
        }


class GroupUsersArrayEnveloped(BaseModel):
    data: list[GroupUser]
    error: Optional[Any] = None


class GroupUserEnveloped(BaseModel):
    data: GroupUser
    error: Optional[Any] = None


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


class ProfileEnveloped(BaseModel):
    data: ProfileOutput
    error: Optional[Any] = None
