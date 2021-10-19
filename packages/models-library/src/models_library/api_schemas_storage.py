"""
    Models used in storage API:

    Specifically services/storage/src/simcore_service_storage/api/v0/openapi.yaml#/components/schemas

    IMPORTANT: DO NOT COUPLE these schemas until storage is refactored
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, constr
from pydantic.networks import AnyUrl

from .basic_regex import UUID_RE
from .generics import ListModel


# /
class HealthCheck(BaseModel):
    name: Optional[str]
    status: Optional[str]
    api_version: Optional[str]
    version: Optional[str]


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


FileLocationArray = ListModel[FileLocation]

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


DatasetMetaDataArray = ListModel[DatasetMetaData]


# /locations/{location_id}/files/metadata:
# /locations/{location_id}/files/{fileId}/metadata:
class FileMetaData(BaseModel):
    file_uuid: Optional[str] = Field(
        description="Unique identifier for a file, like bucket_name/project_id/node_id/file_name = /bucket_name/object_name",
    )

    user_id: Optional[int]
    user_name: Optional[str]

    location_id: Optional[int] = Field(description="Storage location")
    location: Optional[str] = Field(description="Storage location display name")

    bucket_name: Optional[str] = Field(description="Name of the s3 bucket")
    object_name: Optional[str] = Field(
        description="Name of the s3 object within the bucket"
    )

    project_id: Optional[UUID]
    project_name: Optional[str]
    node_id: Optional[UUID]
    node_name: Optional[str]
    file_name: Optional[str] = Field(description="Display name for a file")

    file_id: Optional[str] = Field(
        description="Unique uuid for the file. For simcore.s3: uuid created upon insertion and datcore: datcore uuid",
    )
    raw_file_path: Optional[str] = Field(description="Raw path to file")
    display_file_path: Optional[str] = Field(
        description="Human readlable  path to file"
    )

    created_at: Optional[datetime]
    last_modified: Optional[datetime]
    file_size: Optional[int] = Field(-1, description="File size in bytes")
    entity_tag: Optional[str] = Field(
        description="Entity tag (or ETag), represents a specific version of the file",
    )
    is_soft_link: bool = Field(
        False,
        description="If true, this file is a soft link."
        "i.e. is another entry with the same object_name",
    )

    parent_id: Optional[str]

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
    __root__: List[FileMetaData] = []


# /locations/{location_id}/files/{fileId}


class PresignedLink(BaseModel):
    link: AnyUrl


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
    resource: Optional[str] = Field(description="API resource affected by this error")
    field: Optional[str] = Field(description="Specific field within the resource")


class Level(Enum):
    DEBUG = "DEBUG"
    WARNING = "WARNING"
    INFO = "INFO"
    ERROR = "ERROR"


class LogMessage(BaseModel):
    level: Optional[Level] = Field("INFO", description="Log level")
    message: str = Field(
        ...,
        description="Log message. If logger is USER, then it MUST be human readable",
    )
    logger: Optional[str] = Field(
        description="Name of the logger receiving this message"
    )


class Error(BaseModel):
    logs: Optional[List[LogMessage]] = Field(description="Log messages")
    errors: Optional[List[ErrorItem]] = Field(description="Errors metadata")
    status: Optional[int] = Field(description="HTTP error code")
