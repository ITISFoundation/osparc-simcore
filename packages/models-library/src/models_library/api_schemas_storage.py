"""
    Models used in storage API

    IMPORTANT: do NOT couple these schemas until properly
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, constr

from .basic_regex import UUID_RE


# /
class HealthCheck(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    api_version: Optional[str] = None
    version: Optional[str] = None


class HealthCheckEnveloped(BaseModel):
    data: HealthCheck
    error: Any


# /check/{action}:


class Fake(BaseModel):
    path_value: str
    query_value: str
    body_value: Dict[str, Any]


# /locations


class FileLocation(BaseModel):
    name: str
    id: int

    class Config:
        schema_extra = {
            "examples": [{"name": "simcore.s3", "id": 0}, {"name": "datcore", "id": 1}]
        }


class FileLocationArray(BaseModel):
    __root__: List[FileLocation]


class FileLocationEnveloped(BaseModel):
    data: FileLocation
    error: Any


class FileLocationArrayEnveloped(BaseModel):
    data: FileLocationArray
    error: Any


# /locations/{location_id}/datasets

DatCoreId = constr(regex=r"^N:dataset:" + UUID_RE)


class DatasetMetaData(BaseModel):
    dataset_id: Union[UUID, DatCoreId]
    display_name: str

    class Config:
        schema_extra = {
            "examples": [
                # simcore dataset
                {
                    "dataset_id": "74a84992-8c99-47de-b88a-311c068055ea",
                    "display_name": "api",
                },
                {
                    "dataset_id": "1c46752c-b096-11ea-a3c4-02420a00392e",
                    "display_name": "Octave JupyterLab",
                },
                {
                    "dataset_id": "2de04d1a-f346-11ea-9c22-02420a00085a",
                    "display_name": "Sleepers",
                },
                # datcore datasets
                {
                    "dataset_id": "N:dataset:be862eb8-861e-4b36-afc3-997329dd02bf",
                    "display_name": "simcore-testing-bucket",
                },
                {
                    "dataset_id": "N:dataset:9ad8adb0-8ea2-4be6-bc45-ecbec7546393",
                    "display_name": "YetAnotherTest",
                },
            ]
        }


class DatasetMetaDataArray(BaseModel):
    __root__: List[DatasetMetaData]


class DatasetMetaDataEnveloped(BaseModel):
    data: DatasetMetaData
    error: Any


class DatasetMetaDataArrayEnveloped(BaseModel):
    data: DatasetMetaDataArray
    error: Any


# /locations/{location_id}/files/metadata:
# /locations/{location_id}/files/{fileId}/metadata:
class FileMetaData(BaseModel):
    file_uuid: Optional[str] = None

    location_id: Optional[int] = None
    location: Optional[str] = None

    bucket_name: Optional[str] = None
    object_name: Optional[str] = None

    project_id: Optional[UUID] = None
    project_name: Optional[str] = None
    node_id: Optional[UUID] = None
    node_name: Optional[str] = None
    file_name: Optional[str] = None

    user_id: Optional[int] = None
    user_name: Optional[str] = None

    file_id: Optional[str] = None
    raw_file_path: Optional[str] = None
    display_file_path: Optional[str] = None

    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    file_size: Optional[int] = -1

    parent_id: Optional[str] = None

    class Config:
        schema_extra = {
            "examples": [
                # FIXME: this is the old example and might be wrong!
                {
                    "file_uuid": "simcore-testing/85eef642-e808-4a90-82f5-1ee55da79e25/1000/3",
                    "location_id": "0",
                    "location_name": "simcore.s3",
                    "bucket_name": "simcore-testing",
                    "object_name": "85eef642-e808-4a90-82f5-1ee55da79e25/d5ac1d43-db04-422c-95a1-38b59f45f70b/3",
                    "project_id": "85eef642-e808-4a90-82f5-1ee55da79e25",
                    "project_name": "futurology",
                    "node_id": "d5ac1d43-db04-422c-95a1-38b59f45f70b",
                    "node_name": "alpha",
                    "file_name": "example.txt",
                    "user_id": "12",
                    "user_name": "dennis",
                    "file_id": "N:package:e263da07-2d89-45a6-8b0f-61061b913873",
                    "raw_file_path": "Curation/derivatives/subjects/sourcedata/docs/samples/sam_1/sam_1.csv",
                    "display_file_path": "Curation/derivatives/subjects/sourcedata/docs/samples/sam_1/sam_1.csv",
                    "created_at": "2019-06-19T12:29:03.308611Z",
                    "last_modified": "2019-06-19T12:29:03.78852Z",
                    "file_size": 73,
                    "parent_id": "N:collection:e263da07-2d89-45a6-8b0f-61061b913873",
                },
                {
                    "file_uuid": "1c46752c-b096-11ea-a3c4-02420a00392e/e603724d-4af1-52a1-b866-0d4b792f8c4a/work.zip",
                    "location_id": "0",
                    "location": "simcore.s3",
                    "bucket_name": "master-simcore",
                    "object_name": "1c46752c-b096-11ea-a3c4-02420a00392e/e603724d-4af1-52a1-b866-0d4b792f8c4a/work.zip",
                    "project_id": "1c46752c-b096-11ea-a3c4-02420a00392e",
                    "project_name": "Octave JupyterLab",
                    "node_id": "e603724d-4af1-52a1-b866-0d4b792f8c4a",
                    "node_name": "JupyterLab Octave",
                    "file_name": "work.zip",
                    "user_id": "7",
                    "user_name": None,
                    "file_id": "1c46752c-b096-11ea-a3c4-02420a00392e/e603724d-4af1-52a1-b866-0d4b792f8c4a/work.zip",
                    "raw_file_path": "1c46752c-b096-11ea-a3c4-02420a00392e/e603724d-4af1-52a1-b866-0d4b792f8c4a/work.zip",
                    "display_file_path": "Octave JupyterLab/JupyterLab Octave/work.zip",
                    "created_at": "2020-06-17 12:28:55.705340",
                    "last_modified": "2020-06-22 13:48:13.398000+00:00",
                    "file_size": 17866343,
                    "parent_id": "1c46752c-b096-11ea-a3c4-02420a00392e/e603724d-4af1-52a1-b866-0d4b792f8c4a",
                },
            ]
        }


class FileMetaDataArray(BaseModel):
    __root__: List[FileMetaData]


class FileMetaDataEnveloped(BaseModel):
    data: FileMetaData
    error: Any


class FileMetaDataArrayEnveloped(BaseModel):
    data: FileMetaDataArray
    error: Any


# /locations/{location_id}/files/{fileId}


class PresignedLink(BaseModel):
    link: str


class PresignedLinkEnveloped(BaseModel):
    data: PresignedLink
    error: Any


# /simcore-s3/

# TODO: class Project(BaseModel):


# ERRORS/ LOGS ---------------
#
#


class ErrorItem(BaseModel):
    code: str = Field(
        ...,
        description="Typically the name of the exception that produced it otherwise some known error code",
    )
    message: str = Field(..., description="Error message specific to this item")
    resource: Optional[str] = Field(
        None, description="API resource affected by this error"
    )
    field: Optional[str] = Field(None, description="Specific field within the resource")


class Level(Enum):
    DEBUG = "DEBUG"
    WARNING = "WARNING"
    INFO = "INFO"
    ERROR = "ERROR"


class LogMessage(BaseModel):
    level: Optional[Level] = Field("INFO", description="log level")
    message: str = Field(
        ...,
        description="log message. If logger is USER, then it MUST be human readable",
    )
    logger: Optional[str] = Field(
        None, description="name of the logger receiving this message"
    )


class Error(BaseModel):
    logs: Optional[List[LogMessage]] = Field(None, description="log messages")
    errors: Optional[List[ErrorItem]] = Field(None, description="errors metadata")
    status: Optional[int] = Field(None, description="HTTP error code")


class LogMessageEnveloped(BaseModel):
    data: LogMessage
    error: Any


class FakeEnveloped(BaseModel):
    data: Fake
    error: Any


class ErrorEnveloped(BaseModel):
    data: Any
    error: Error
