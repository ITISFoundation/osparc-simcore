from datetime import datetime
from enum import auto
from typing import TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    ValidationInfo,
    field_validator,
)

from .access_rights import AccessRights
from .users import GroupID, UserID
from .utils.enums import StrAutoEnum
from .workspaces import WorkspaceID

FolderID: TypeAlias = PositiveInt


class FolderScope(StrAutoEnum):
    ROOT = auto()
    SPECIFIC = auto()
    ALL = auto()


class FolderQuery(BaseModel):
    folder_scope: FolderScope
    folder_id: PositiveInt | None = None

    @field_validator("folder_id", mode="before")
    @classmethod
    def validate_folder_id(cls, value, info: ValidationInfo):
        scope = info.data.get("folder_scope")
        if scope == FolderScope.SPECIFIC and value is None:
            msg = "folder_id must be provided when folder_scope is SPECIFIC."
            raise ValueError(msg)
        if scope != FolderScope.SPECIFIC and value is not None:
            msg = "folder_id should be None when folder_scope is not SPECIFIC."
            raise ValueError(msg)
        return value


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
    trashed_at: datetime | None = Field(
        ...,
    )

    user_id: UserID | None
    workspace_id: WorkspaceID | None

    model_config = ConfigDict(from_attributes=True)


class UserFolderAccessRightsDB(FolderDB):
    my_access_rights: AccessRights

    model_config = ConfigDict(from_attributes=True)
