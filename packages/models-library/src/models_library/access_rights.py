from pydantic import BaseModel, Extra, Field


class AccessRights(BaseModel):
    read: bool = Field(..., description="has read access")
    write: bool = Field(..., description="has write access")
    delete: bool = Field(..., description="has deletion rights")

    class Config:
        extra = Extra.forbid
