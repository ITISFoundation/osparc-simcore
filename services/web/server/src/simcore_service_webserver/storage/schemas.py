from enum import Enum
from typing import Any, TypeAlias

from models_library.api_schemas_storage import TableSynchronisation
from pydantic import BaseModel, ConfigDict, Field, RootModel

# NOTE: storage generates URLs that contain double encoded
# slashes, and when applying validation via `StorageFileID`
# it raises an error. Before `StorageFileID`, `str` was the
# type used in the OpenAPI specs.
StorageFileIDStr: TypeAlias = str


class FileLocation(BaseModel):
    name: str | None = None
    id: float | None = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "simcore.s3",
                "id": 0,
            },
        }
    )


class FileLocationArray(RootModel[list[FileLocation]]):
    ...


class Links(BaseModel):
    abort_upload: str
    complete_upload: str


class FileUploadSchema(BaseModel):
    chunk_size: int = Field(..., ge=0)
    urls: list[str]
    links: Links


class Links1(BaseModel):
    state: str


class FileUploadComplete(BaseModel):
    links: Links1


class State(str, Enum):
    ok = "ok"
    nok = "nok"


class FileUploadCompleteFuture(BaseModel):
    state: State
    e_tag: str | None = None


class DatasetMetaData(BaseModel):
    dataset_id: str | None = None
    display_name: str | None = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "dataset_id": "N:id-aaaa",
                "display_name": "simcore-testing",
            },
        }
    )


class DatasetMetaDataArray(RootModel[list[DatasetMetaData]]):
    ...


class FileLocationEnveloped(BaseModel):
    data: FileLocation
    error: Any | None = None


class TableSynchronisationEnveloped(BaseModel):
    data: TableSynchronisation
    error: Any


class FileUploadEnveloped(BaseModel):
    data: FileUploadSchema
    error: Any


class FileUploadCompleteEnveloped(BaseModel):
    data: FileUploadComplete
    error: Any


class FileUploadCompleteFutureEnveloped(BaseModel):
    data: FileUploadCompleteFuture
    error: Any


class DatasetMetaEnvelope(BaseModel):
    data: DatasetMetaData
    error: Any | None = None


class CompleteUpload(BaseModel):
    number: int = Field(..., ge=1)
    e_tag: str


class FileMetaData(BaseModel):
    file_uuid: str | None = None
    location_id: str | None = None
    project_name: str | None = None
    node_name: str | None = None
    file_name: str | None = None
    file_id: str | None = None
    created_at: str | None = None
    last_modified: str | None = None
    file_size: int | None = None
    entity_tag: str | None = None
    is_directory: bool | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_uuid": "simcore-testing/105/1000/3",
                "location_id": "0",
                "project_name": "futurology",
                "node_name": "alpha",
                "file_name": "example.txt",
                "file_id": "N:package:e263da07-2d89-45a6-8b0f-61061b913873",
                "created_at": "2019-06-19T12:29:03.308611Z",
                "last_modified": "2019-06-19T12:29:03.78852Z",
                "file_size": 73,
                "entity_tag": "a87ff679a2f3e71d9181a67b7542122c",
                "is_directory": False,
            }
        }
    )


class FileMetaDataArray(RootModel[list[FileMetaData]]):
    ...


class FileMetaEnvelope(BaseModel):
    data: FileMetaData
    error: Any | None = None


class PresignedLink(BaseModel):
    link: str | None = None

    model_config = ConfigDict(json_schema_extra={"example": {"link": "example_link"}})


class PresignedLinkEnveloped(BaseModel):
    data: PresignedLink
    error: Any | None = None
