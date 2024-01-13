"""
    Ownership and access rights
"""

import re
from enum import Enum

from models_library.users import FirstNameStr, LastNameStr
from pydantic import BaseModel, Extra, Field, validator
from pydantic.types import ConstrainedStr, PositiveInt

from .utils.common_validators import none_to_empty_str_pre_validator


class GroupIDStr(ConstrainedStr):
    regex = re.compile(r"^\S+$")

    class Config:
        frozen = True


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
    first_name: FirstNameStr = Field(
        ..., description="Owner first name", examples=["John"]
    )
    last_name: LastNameStr = Field(
        ..., description="Owner last name", examples=["Smith"]
    )

    class Config:
        extra = Extra.forbid

    _none_is_empty = validator("first_name", "last_name", allow_reuse=True, pre=True)(
        none_to_empty_str_pre_validator
    )
