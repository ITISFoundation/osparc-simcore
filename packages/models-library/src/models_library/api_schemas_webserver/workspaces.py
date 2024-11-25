from datetime import datetime
from typing import NamedTuple

from models_library.basic_types import IDStr
from models_library.users import GroupID
from models_library.workspaces import WorkspaceID
from pydantic import ConfigDict, PositiveInt

from ..access_rights import AccessRights
from ..users import UserID
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


class WorkspaceGetPage(NamedTuple):
    items: list[WorkspaceGet]
    total: PositiveInt


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
