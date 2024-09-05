from datetime import datetime
from typing import NamedTuple

from models_library.access_rights import AccessRights
from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.users import GroupID
from models_library.utils.common_validators import null_or_none_str_to_none_validator
from models_library.workspaces import WorkspaceID
from pydantic import Extra, PositiveInt, validator

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

    class Config:
        extra = Extra.forbid

    _null_or_none_str_to_none_validator = validator(
        "parent_folder_id", allow_reuse=True, pre=True
    )(null_or_none_str_to_none_validator)

    _null_or_none_str_to_none_validator2 = validator(
        "workspace_id", allow_reuse=True, pre=True
    )(null_or_none_str_to_none_validator)


class PutFolderBodyParams(InputSchema):
    name: IDStr
    parent_folder_id: FolderID | None

    class Config:
        extra = Extra.forbid

    _null_or_none_str_to_none_validator = validator(
        "parent_folder_id", allow_reuse=True, pre=True
    )(null_or_none_str_to_none_validator)
