from typing import List, Optional

from pydantic import BaseModel, Field


class UsersGroup(BaseModel):
    gid: str
    label: str
    description: Optional[str] = None


class Groups(BaseModel):
    me: UsersGroup
    organizations: Optional[List[UsersGroup]] = []
    all_: UsersGroup = Field(..., alias="all")
