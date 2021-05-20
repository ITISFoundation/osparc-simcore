from typing import Optional

from pydantic import BaseModel, Field
from pydantic.types import PositiveInt

from ...db.tables import GroupType


class Group(BaseModel):
    gid: PositiveInt
    name: str
    description: str
    group_type: GroupType = Field(..., alias="type")
    thumbnail: Optional[str]


class GroupAtDB(Group):
    class Config:
        orm_mode = True

        schema_extra = {
            "example": {
                "gid": 218,
                "name": "Friends group",
                "description": "Joey, Ross, Rachel, Monica, Phoeby and Chandler",
                "type": GroupType.STANDARD,
                "thumbnail": "https://image.flaticon.com/icons/png/512/23/23374.png",
            }
        }
