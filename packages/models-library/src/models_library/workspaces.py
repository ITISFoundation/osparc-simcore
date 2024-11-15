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
from .users import GroupID
from .utils.enums import StrAutoEnum

WorkspaceID: TypeAlias = PositiveInt


class WorkspaceScope(StrAutoEnum):
    PRIVATE = auto()
    SHARED = auto()
    ALL = auto()


class WorkspaceQuery(BaseModel):
    workspace_scope: WorkspaceScope
    workspace_id: PositiveInt | None = None

    @field_validator("workspace_id", mode="before")
    @classmethod
    def validate_workspace_id(cls, value, info: ValidationInfo):
        scope = info.data.get("workspace_scope")
        if scope == WorkspaceScope.SHARED and value is None:
            msg = "workspace_id must be provided when workspace_scope is SHARED."
            raise ValueError(msg)
        if scope != WorkspaceScope.SHARED and value is not None:
            msg = "workspace_id should be None when workspace_scope is not SHARED."
            raise ValueError(msg)
        return value


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

    model_config = ConfigDict(from_attributes=True)


class UserWorkspaceAccessRightsDB(WorkspaceDB):
    my_access_rights: AccessRights
    access_rights: dict[GroupID, AccessRights]

    model_config = ConfigDict(from_attributes=True)
