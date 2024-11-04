from datetime import datetime
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from .users import GroupID, UserID
from .workspaces import WorkspaceID

FolderID: TypeAlias = PositiveInt


#
# DB
#


class FolderDB(BaseModel):
    folder_id: FolderID
    name: str
    parent_folder_id: FolderID | None
    created_by_gid: GroupID = Field(
        ...,
        description="GID of the group that owns this wallet",
    )
    created: datetime = Field(
        ...,
        description="Timestamp on creation",
    )
    modified: datetime = Field(
        ...,
        description="Timestamp of last modification",
    )
    user_id: UserID | None
    workspace_id: WorkspaceID | None

    model_config = ConfigDict(from_attributes=True)
