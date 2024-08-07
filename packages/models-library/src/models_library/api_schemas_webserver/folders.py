from datetime import datetime

from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.projects_access import AccessRights
from models_library.users import GroupID

from ._base import InputSchema, OutputSchema


class FolderGet(OutputSchema):
    folder_id: FolderID
    parent_folder_id: FolderID | None
    name: str
    description: str
    created_at: datetime
    modified_at: datetime
    owner: GroupID
    my_access_rights: AccessRights
    access_rights: dict[GroupID, AccessRights]


class CreateFolderBodyParams(InputSchema):
    name: IDStr
    description: IDStr
    parent_folder_id: FolderID | None


class PutFolderBodyParams(InputSchema):
    name: IDStr
    description: IDStr
