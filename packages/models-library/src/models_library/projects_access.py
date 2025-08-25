"""
Ownership and access rights
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .basic_types import IDStr
from .users import UserID


class GroupIDStr(IDStr): ...


class AccessEnum(str, Enum):
    READANDWRITE = "ReadAndWrite"
    INVISIBLE = "Invisible"
    READONLY = "ReadOnly"


class AccessRights(BaseModel):
    read: Annotated[bool, Field(description="has read access")]
    write: Annotated[bool, Field(description="has write access")]
    delete: Annotated[bool, Field(description="has deletion rights")]

    model_config = ConfigDict(extra="forbid")


class Owner(BaseModel):
    user_id: Annotated[UserID, Field(description="Owner's user id")]

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"user_id": 1},
                {"user_id": 42},
                {"user_id": 666},
            ]
        },
    )
