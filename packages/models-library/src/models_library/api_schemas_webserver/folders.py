from models_library.folders import FolderID

from ._base import OutputSchema


class FolderGet(OutputSchema):
    folder_id: FolderID


class CreateFolderBodyParams(OutputSchema):
    name: str
    description: str


class PutFolderBodyParams(OutputSchema):
    name: str
    description: str
