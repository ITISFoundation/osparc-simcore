from datetime import datetime

from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.projects_access import AccessRights
from models_library.users import GroupID
from pydantic import Extra

from ._base import InputSchema, OutputSchema


class FolderGet(OutputSchema):
    folder_id: FolderID
    parent_folder_id: FolderID | None = None
    name: str
    description: str
    created_at: datetime
    modified_at: datetime
    owner: GroupID
    my_access_rights: AccessRights
    access_rights: dict[GroupID, AccessRights]


class CreateFolderBodyParams(InputSchema):
    name: IDStr
    description: str
    parent_folder_id: FolderID | None = None

    class Config:
        extra = Extra.forbid


class PutFolderBodyParams(InputSchema):
    name: IDStr
    description: str

    class Config:
        extra = Extra.forbid
