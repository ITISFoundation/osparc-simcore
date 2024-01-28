"""
    Ownership and access rights
"""

from enum import Enum

from models_library.basic_types import IDStr
from models_library.users import FirstNameStr, LastNameStr
from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import PositiveInt


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
    @classmethod
    # TODO[pydantic]: We couldn't refactor `__modify_schema__`, please create the `__get_pydantic_json_schema__` manually.
    # Check https://docs.pydantic.dev/latest/migration/#defining-custom-types for more information.
    def __modify_schema__(cls, field_schema):
        field_schema.pop("exclusiveMinimum", None)


class Owner(BaseModel):
    user_id: PositiveIntWithExclusiveMinimumRemoved = Field(
        ..., description="Owner's user id"
    )
    first_name: FirstNameStr | None = Field(..., description="Owner's first name")
    last_name: LastNameStr | None = Field(..., description="Owner's last name")
    model_config = ConfigDict(extra="forbid")
