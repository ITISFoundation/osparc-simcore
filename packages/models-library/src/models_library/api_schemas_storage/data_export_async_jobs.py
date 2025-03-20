# pylint: disable=R6301

from common_library.errors_classes import OsparcErrorMixin
from models_library.projects_nodes_io import LocationID, StorageFileID
from pydantic import BaseModel, Field


class DataExportTaskStartInput(BaseModel):
    location_id: LocationID
    file_and_folder_ids: list[StorageFileID] = Field(..., min_length=1)


### Exceptions


class StorageRpcBaseError(OsparcErrorMixin, RuntimeError):
    pass


class InvalidFileIdentifierError(StorageRpcBaseError):
    msg_template: str = "Could not find the file {file_id}"


class AccessRightError(StorageRpcBaseError):
    msg_template: str = (
        "User {user_id} does not have access to file {file_id} with location {location_id}"
    )
