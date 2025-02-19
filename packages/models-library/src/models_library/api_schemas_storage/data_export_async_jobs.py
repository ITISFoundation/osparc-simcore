# pylint: disable=R6301
from pathlib import Path

from common_library.errors_classes import OsparcErrorMixin
from models_library.projects_nodes_io import LocationID
from models_library.users import UserID
from pydantic import BaseModel, Field


class DataExportTaskStartInput(BaseModel):
    user_id: UserID
    location_id: LocationID
    paths: list[Path] = Field(..., min_length=1)


### Exceptions


class StorageRpcError(OsparcErrorMixin, RuntimeError):
    pass


class InvalidFileIdentifierError(StorageRpcError):
    msg_template: str = "Could not find the file {file_id}"


class AccessRightError(StorageRpcError):
    msg_template: str = "User {user_id} does not have access to file {file_id}"


class DataExportError(StorageRpcError):
    msg_template: str = "Could not complete data export job with id {job_id}"
