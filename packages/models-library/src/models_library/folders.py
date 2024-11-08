from datetime import datetime
from enum import auto
from typing import TypeAlias

from pydantic import BaseModel, Field, PositiveInt, validator

from .users import GroupID, UserID
from .utils.enums import StrAutoEnum

FolderID: TypeAlias = PositiveInt


class FolderScope(StrAutoEnum):
    ROOT = auto()
    SPECIFIC = auto()
    ALL = auto()


class FolderQuery(BaseModel):
    folder_scope: FolderScope
    folder_id: PositiveInt | None = None

    @validator("folder_id", pre=True, always=True)
    @classmethod
    def validate_folder_id(cls, value, values):
        scope = values.get("folder_scope")
        if scope == FolderScope.SPECIFIC and value is None:
            raise ValueError(
                "folder_id must be provided when folder_scope is SPECIFIC."
            )
        if scope != FolderScope.SPECIFIC and value is not None:
            raise ValueError(
                "folder_id should be None when folder_scope is not SPECIFIC."
            )
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
    folder_id: FolderID | None

    class Config:
        orm_mode = True
