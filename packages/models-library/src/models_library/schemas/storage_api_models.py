"""
    Models used in storage API
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..projects import Project as CommonProject


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
    name: Optional[str] = None
    id: Optional[int] = None


class FileLocationArray(BaseModel):
    __root__: List[FileLocation]


class FileLocationEnveloped(BaseModel):
    data: FileLocation
    error: Any


class FileLocationArrayEnveloped(BaseModel):
    data: FileLocationArray
    error: Any


# /locations/{location_id}/datasets


class DatasetMetaData(BaseModel):
    dataset_id: Optional[str] = None
    display_name: Optional[str] = None


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
    location_id: Optional[str] = None
    location: Optional[str] = None
    bucket_name: Optional[str] = None
    object_name: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    node_id: Optional[str] = None
    node_name: Optional[str] = None
    file_name: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    file_id: Optional[str] = None
    raw_file_path: Optional[str] = None
    display_file_path: Optional[str] = None
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    file_size: Optional[int] = None
    parent_id: Optional[str] = None

    class Config:
        schema_extra = {
            "examples": [
                {
                    "file_uuid": "simcore-testing/105/1000/3",
                    "location_id": "0",
                    "location_name": "simcore.s3",
                    "bucket_name": "simcore-testing",
                    "object_name": "105/10000/3",
                    "project_id": "105",
                    "project_name": "futurology",
                    "node_id": "10000",
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
                }
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


class Project(BaseModel):
    __root__: CommonProject


# ERRORS/ LOGS ---------------


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
