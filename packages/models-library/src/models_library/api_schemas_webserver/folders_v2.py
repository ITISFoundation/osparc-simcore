from datetime import datetime
from typing import NamedTuple

from pydantic import ConfigDict, PositiveInt, field_validator

from ..access_rights import AccessRights
from ..basic_types import IDStr
from ..folders import FolderID
from ..users import GroupID
from ..utils.common_validators import null_or_none_str_to_none_validator
from ..workspaces import WorkspaceID
from ._base import InputSchema, OutputSchema


class FolderGet(OutputSchema):
    folder_id: FolderID
    parent_folder_id: FolderID | None = None
    name: str
    created_at: datetime
    modified_at: datetime
    trashed_at: datetime | None
    owner: GroupID
    workspace_id: WorkspaceID | None
    my_access_rights: AccessRights


class FolderGetPage(NamedTuple):
    items: list[FolderGet]
    total: PositiveInt


class FolderCreateBodyParams(InputSchema):
    name: IDStr
    parent_folder_id: FolderID | None = None
    workspace_id: WorkspaceID | None = None
    model_config = ConfigDict(extra="forbid")

    _null_or_none_str_to_none_validator = field_validator(
        "parent_folder_id", mode="before"
    )(null_or_none_str_to_none_validator)

    _null_or_none_str_to_none_validator2 = field_validator(
        "workspace_id", mode="before"
    )(null_or_none_str_to_none_validator)


class FolderReplaceBodyParams(InputSchema):
    name: IDStr
    parent_folder_id: FolderID | None = None
    model_config = ConfigDict(extra="forbid")

    _null_or_none_str_to_none_validator = field_validator(
        "parent_folder_id", mode="before"
    )(null_or_none_str_to_none_validator)
