from pydantic import BaseModel, Field


class UsersGroup(BaseModel):
    gid: str
    label: str
    description: str | None = None


class Groups(BaseModel):
    me: UsersGroup
    organizations: list[UsersGroup] | None = []
    all_: UsersGroup = Field(..., alias="all")
