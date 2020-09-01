from typing import List

from pydantic import BaseModel, Field

from .items import Item


class User(BaseModel):
    uid: int = Field(..., alias="id")
    is_active: bool
    items: List[Item] = []

    class Config:
        orm_mode = True
