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


class PositiveIntWithExclusiveMinimumRemoved(PositiveInt):
    # As we are trying to match this Pydantic model to a historical json schema "project-v0.0.1" we need to remove this
    # Pydantic does not support exclusiveMinimum boolean https://github.com/pydantic/pydantic/issues/4108
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.pop("exclusiveMinimum", None)


class Owner(BaseModel):
    user_id: PositiveIntWithExclusiveMinimumRemoved = Field(
        ...,
        description="Owner's identifier when registered in the user's database table",
        examples=[2],
    )
    first_name: str = Field(..., description="Owner first name", examples=["John"])
    last_name: str = Field(..., description="Owner last name", examples=["Smith"])

    class Config:
        extra = Extra.forbid
