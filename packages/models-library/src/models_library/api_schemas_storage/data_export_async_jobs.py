# pylint: disable=R6301
from pathlib import Path

from common_library.errors_classes import OsparcErrorMixin
from models_library.projects_nodes_io import LocationID
from pydantic import BaseModel, Field


class DataExportTaskStartInput(BaseModel):
    location_id: LocationID
    paths: list[Path] = Field(..., min_length=1)


### Exceptions


class StorageRpcErrors(OsparcErrorMixin, RuntimeError):
    pass


class InvalidFileIdentifierError(StorageRpcErrors):
    msg_template: str = "Could not find the file {file_id}"


class AccessRightError(StorageRpcErrors):
    msg_template: str = "User {user_id} does not have access to file {file_id}"


class DataExportError(StorageRpcErrors):
    msg_template: str = "Could not complete data export job with id {job_id}"
