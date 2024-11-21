from datetime import datetime
from typing import NamedTuple

from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.projects_access import AccessRights
from models_library.users import GroupID
from models_library.utils.common_validators import null_or_none_str_to_none_validator
from pydantic import ConfigDict, PositiveInt, field_validator

from ._base import InputSchema, OutputSchema


class FolderGet(OutputSchema):
    folder_id: FolderID
    parent_folder_id: FolderID | None = None
    name: str
    description: str
    created_at: datetime
    modified_at: datetime
    trashed_at: datetime | None
    owner: GroupID
    my_access_rights: AccessRights
    access_rights: dict[GroupID, AccessRights]


class FolderGetPage(NamedTuple):
    items: list[FolderGet]
    total: PositiveInt


class CreateFolderBodyParams(InputSchema):
    name: IDStr
    description: str
    parent_folder_id: FolderID | None = None

    model_config = ConfigDict(extra="forbid")

    _null_or_none_str_to_none_validator = field_validator(
        "parent_folder_id", mode="before"
    )(null_or_none_str_to_none_validator)


class PutFolderBodyParams(InputSchema):
    name: IDStr
    description: str

    model_config = ConfigDict(extra="forbid")
