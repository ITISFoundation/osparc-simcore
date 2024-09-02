from datetime import datetime
from typing import TypeAlias

from pydantic import BaseModel, Field, PositiveInt

WorkspaceID: TypeAlias = PositiveInt


#
# DB
#


class WorkspaceDB(BaseModel):
    workspace_id: WorkspaceID
    name: str
    description: str | None
    owner_primary_gid: PositiveInt = Field(
        ...,
        description="GID of the group that owns this wallet",
    )
    thumbnail: str | None
    created: datetime = Field(
        ...,
        description="Timestamp on creation",
    )
    modified: datetime = Field(
        ...,
        description="Timestamp of last modification",
    )

    class Config:
        orm_mode = True


class UserWorkspaceAccessRightsDB(WorkspaceDB):
    read: bool
    write: bool
    delete: bool

    class Config:
        orm_mode = True
