from datetime import datetime

from models_library.basic_types import IDStr
from models_library.folders import FolderID

from ._base import InputSchema, OutputSchema


class FolderGet(OutputSchema):
    folder_id: FolderID
    name: str
    description: str
    modified_at: datetime


class CreateFolderBodyParams(InputSchema):
    name: IDStr
    description: IDStr
    parent_folder_id: FolderID | None


class PutFolderBodyParams(InputSchema):
    name: IDStr
    description: IDStr
