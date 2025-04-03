from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class AccessRights(BaseModel):
    read: Annotated[bool, Field(description="has read access")]
    write: Annotated[bool, Field(description="has write access")]
    delete: Annotated[bool, Field(description="has deletion rights")]

    model_config = ConfigDict(extra="forbid")

    def check_access_constraints(self):
        """Helper function that checks extra constraints in access-rights flags"""
        if self.write and not self.read:
            msg = "Write access requires read access"
            raise ValueError(msg)
        if self.delete and not self.write:
            msg = "Delete access requires read access"
            raise ValueError(msg)
        return self


class ExecutableAccessRights(BaseModel):
    write: Annotated[bool, Field(description="can change executable settings")]
    execute: Annotated[bool, Field(description="can run executable")]

    model_config = ConfigDict(extra="forbid")
