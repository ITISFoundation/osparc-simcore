from pydantic import BaseModel, Field


class UsersGroup(BaseModel):
    gid: str
    label: str
    description: str = None  # TODO: should be nullable


class Groups(BaseModel):
    me: UsersGroup
    organizations: list[UsersGroup] = []  # TODO: should be nullable
    all_: UsersGroup = Field(..., alias="all")
