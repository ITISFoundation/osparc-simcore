from datetime import datetime
from typing import TypeAlias

from models_library.users import GroupID
from pydantic import BaseModel, Field, PositiveInt

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
