from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, conint


class FileLocation(BaseModel):
    name: Optional[str] = None
    id: Optional[float] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "simcore.s3",
                "id": 0,
            },
        }


class FileLocationArray(BaseModel):
    __root__: list[FileLocation]


class TableSynchronisation(BaseModel):
    dry_run: Optional[bool] = None
    fire_and_forget: Optional[bool] = None
    removed: list[str]


class Links(BaseModel):
    abort_upload: str
    complete_upload: str


class FileUploadSchema(BaseModel):
    chunk_size: conint(ge=0)
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
    e_tag: Optional[str] = None


class DatasetMetaData(BaseModel):
    dataset_id: Optional[str] = None
    display_name: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "dataset_id": "N:id-aaaa",
                "display_name": "simcore-testing",
            },
        }


class DatasetMetaDataArray(BaseModel):
    __root__: list[DatasetMetaData]


class FileLocationEnveloped(BaseModel):
    data: FileLocation
    error: Optional[Any] = None


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
    error: Optional[Any] = None


class CompleteUpload(BaseModel):
    number: int = Field(..., ge=1)
    e_tag: str


class FileMetaData(BaseModel):
    file_uuid: Optional[str] = None
    location_id: Optional[str] = None
    project_name: Optional[str] = None
    node_name: Optional[str] = None
    file_name: Optional[str] = None
    file_id: Optional[str] = None
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    file_size: Optional[int] = None
    entity_tag: Optional[str] = None

    class Config:
        schema_extra = {
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
            }
        }


class FileMetaDataArray(BaseModel):
    __root__: list[FileMetaData]


class FileMetaEnvelope(BaseModel):
    data: FileMetaData
    error: Optional[Any] = None


class PresignedLink(BaseModel):
    link: Optional[str] = None

    class Config:
        schema_extra = {"example": {"link": "example_link"}}


class PresignedLinkEnveloped(BaseModel):
    data: PresignedLink
    error: Optional[Any] = None
