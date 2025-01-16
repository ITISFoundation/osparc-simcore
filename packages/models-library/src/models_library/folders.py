from datetime import datetime
from enum import auto
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, PositiveInt, ValidationInfo, field_validator

from .access_rights import AccessRights
from .groups import GroupID
from .users import UserID
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

    created_by_gid: GroupID
    created: datetime
    modified: datetime

    trashed: datetime | None
    trashed_by: UserID | None
    trashed_explicitly: bool

    user_id: UserID | None  # owner?
    workspace_id: WorkspaceID | None
    model_config = ConfigDict(from_attributes=True)


class UserFolderAccessRightsDB(FolderDB):
    my_access_rights: AccessRights

    model_config = ConfigDict(from_attributes=True)
