from pydantic import BaseModel, Field


class ItemBase(BaseModel):
    title: str
    description: str = None


class Item(ItemBase):
    id_: int = Field(..., alias="id")
    owner_id: int

    class Config:
        orm_mode = True
