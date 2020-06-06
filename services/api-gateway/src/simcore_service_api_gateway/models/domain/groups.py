from pydantic import BaseModel, Field


class UsersGroup(BaseModel):
    gid: str
    label: str
    description: str


class Groups(BaseModel):
    me: UsersGroup
    organizations: UsersGroup
    all_: UsersGroup = Field(..., alias="all")
