"""
    Ownership and access rights
"""

from enum import Enum

from pydantic import BaseModel, Extra, Field, constr
from pydantic.types import PositiveInt

GroupIDStr = constr(regex=r"^\S+$")


class AccessEnum(str, Enum):
    READANDWRITE = "ReadAndWrite"
    INVISIBLE = "Invisible"
    READONLY = "ReadOnly"


class AccessRights(BaseModel):
    read: bool = Field(..., description="gives read access")
    write: bool = Field(..., description="gives write access")
    delete: bool = Field(..., description="gives deletion rights")

    class Config:
        extra = Extra.forbid


class Owner(BaseModel):
    user_id: PositiveInt = Field(
        ...,
        description="Owner's identifier when registered in the user's database table",
        examples=[2],
    )
    first_name: str = Field(..., description="Owner first name", examples=["John"])
    last_name: str = Field(..., description="Owner last name", examples=["Smith"])

    class Config:
        extra = Extra.forbid
