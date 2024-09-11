"""
    Ownership and access rights
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import PositiveInt

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


class Owner(BaseModel):
    user_id: PositiveInt = Field(..., description="Owner's user id")
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
    )
