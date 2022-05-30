from typing import Optional

from pydantic import BaseModel, Field


class UsersGroup(BaseModel):
    gid: str
    label: str
    description: Optional[str] = None


class Groups(BaseModel):
    me: UsersGroup
    organizations: Optional[list[UsersGroup]] = []
    all_: UsersGroup = Field(..., alias="all")
