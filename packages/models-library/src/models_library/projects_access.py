"""
    Ownership and access rights
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from .basic_types import IDStr
from .users import FirstNameStr, LastNameStr


class GroupIDStr(IDStr):
    ...


class AccessEnum(str, Enum):
    READANDWRITE = "ReadAndWrite"
    INVISIBLE = "Invisible"
    READONLY = "ReadOnly"


class AccessRights(BaseModel):
    read: bool = Field(..., description="has read access")
    write: bool = Field(..., description="has write access")
    delete: bool = Field(..., description="has deletion rights")
    model_config = ConfigDict(extra="forbid")


class PositiveIntWithExclusiveMinimumRemoved(PositiveInt):
    # As we are trying to match this Pydantic model to a historical json schema "project-v0.0.1" we need to remove this
    # Pydantic does not support exclusiveMinimum boolean https://github.com/pydantic/pydantic/issues/4108
    @staticmethod
    def __schema_extra__(schema: dict[str, Any], _handler: Any) -> None:
        # Remove "exclusiveMinimum" from the schema if it exists
        if "exclusiveMinimum" in schema:
            schema.pop("exclusiveMinimum")


class Owner(BaseModel):
    user_id: PositiveIntWithExclusiveMinimumRemoved = Field(
        ..., description="Owner's user id"
    )
    first_name: FirstNameStr | None = Field(..., description="Owner's first name")
    last_name: LastNameStr | None = Field(..., description="Owner's last name")

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                # NOTE: None and empty string are both defining an undefined value
                {"user_id": 1, "first_name": None, "last_name": None},
                {"user_id": 2, "first_name": "", "last_name": ""},
                {"user_id": 3, "first_name": "John", "last_name": "Smith"},
            ]
        },
        arbitrary_types_allowed=True,
    )
