from datetime import datetime
from typing import Self

from models_library.basic_types import IDStr
from models_library.groups import GroupID
from models_library.workspaces import WorkspaceID
from pydantic import ConfigDict

from ..access_rights import AccessRights
from ..users import UserID
from ..workspaces import UserWorkspaceAccessRightsDB, WorkspaceID
from ._base import InputSchema, OutputSchema


class WorkspaceGet(OutputSchema):
    workspace_id: WorkspaceID
    name: str
    description: str | None
    thumbnail: str | None
    created_at: datetime
    modified_at: datetime
    trashed_at: datetime | None
    trashed_by: UserID | None
    my_access_rights: AccessRights
    access_rights: dict[GroupID, AccessRights]

    @classmethod
    def from_model(cls, workspace_db: UserWorkspaceAccessRightsDB) -> Self:
        return cls(
            workspace_id=workspace_db.workspace_id,
            name=workspace_db.name,
            description=workspace_db.description,
            thumbnail=workspace_db.thumbnail,
            created_at=workspace_db.created,
            modified_at=workspace_db.modified,
            trashed_at=workspace_db.trashed,
            trashed_by=workspace_db.trashed_by if workspace_db.trashed else None,
            my_access_rights=workspace_db.my_access_rights,
            access_rights=workspace_db.access_rights,
        )


class WorkspaceCreateBodyParams(InputSchema):
    name: str
    description: str | None = None
    thumbnail: str | None = None

    model_config = ConfigDict(extra="forbid")


class WorkspaceReplaceBodyParams(InputSchema):
    name: IDStr
    description: str | None = None
    thumbnail: str | None = None

    model_config = ConfigDict(extra="forbid")
