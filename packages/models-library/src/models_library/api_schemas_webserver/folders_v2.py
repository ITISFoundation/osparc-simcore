from datetime import datetime
from typing import NamedTuple

from common_library.pydantic_basic_types import IDStr
from models_library.access_rights import AccessRights
from models_library.folders import FolderID
from models_library.users import GroupID
from models_library.utils.common_validators import null_or_none_str_to_none_validator
from models_library.workspaces import WorkspaceID
from pydantic import ConfigDict, PositiveInt, field_validator

from ._base import InputSchema, OutputSchema


class FolderGet(OutputSchema):
    folder_id: FolderID
    parent_folder_id: FolderID | None = None
    name: str
    created_at: datetime
    modified_at: datetime
    owner: GroupID
    workspace_id: WorkspaceID | None
    my_access_rights: AccessRights


class FolderGetPage(NamedTuple):
    items: list[FolderGet]
    total: PositiveInt


class CreateFolderBodyParams(InputSchema):
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


class PutFolderBodyParams(InputSchema):
    name: IDStr
    parent_folder_id: FolderID | None
    model_config = ConfigDict(extra="forbid")

    _null_or_none_str_to_none_validator = field_validator(
        "parent_folder_id", mode="before"
    )(null_or_none_str_to_none_validator)
