from datetime import datetime
from typing import Self

from pydantic import ConfigDict

from ..access_rights import AccessRights
from ..basic_types import IDStr
from ..groups import GroupID
from ..users import UserID
from ..workspaces import UserWorkspaceWithAccessRights, WorkspaceID
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
    def from_domain_model(cls, wks: UserWorkspaceWithAccessRights) -> Self:
        return cls(
            workspace_id=wks.workspace_id,
            name=wks.name,
            description=wks.description,
            thumbnail=wks.thumbnail,
            created_at=wks.created,
            modified_at=wks.modified,
            trashed_at=wks.trashed,
            trashed_by=wks.trashed_by if wks.trashed else None,
            my_access_rights=wks.my_access_rights,
            access_rights=wks.access_rights,
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
