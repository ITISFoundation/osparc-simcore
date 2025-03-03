from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class AccessRights(BaseModel):
    read: Annotated[bool, Field(description="has read access")]
    write: Annotated[bool, Field(description="has write access")]
    delete: Annotated[bool, Field(description="has deletion rights")]

    model_config = ConfigDict(extra="forbid")


class ExecutableAccessRights(BaseModel):
    write: Annotated[bool, Field(description="can change executable settings")]
    execute: Annotated[bool, Field(description="can run executable")]

    model_config = ConfigDict(extra="forbid")
