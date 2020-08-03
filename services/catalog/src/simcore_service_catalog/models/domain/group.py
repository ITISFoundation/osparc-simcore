from typing import Optional

from pydantic import BaseModel, Field
from ...db.tables import GroupType


class Group(BaseModel):
    gid: int
    name: str
    description: str
    group_type: GroupType = Field(..., alias="type")
    thumbnail: Optional[str]


class GroupAtDB(Group):
    class Config:
        orm_mode = True
