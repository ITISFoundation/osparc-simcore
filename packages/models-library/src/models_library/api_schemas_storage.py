"""
    Models used in storage API:

    Specifically services/storage/src/simcore_service_storage/api/v0/openapi.yaml#/components/schemas

    IMPORTANT: DO NOT COUPLE these schemas until storage is refactored
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Union

from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, LocationName, StorageFileID
from pydantic import BaseModel, ByteSize, ConstrainedStr, Extra, Field, validator
from pydantic.networks import AnyUrl

from .basic_regex import DATCORE_DATASET_NAME_RE, S3_BUCKET_NAME_RE
from .generics import ListModel

ETag = str


class S3BucketName(ConstrainedStr):
    regex: Optional[Pattern[str]] = re.compile(S3_BUCKET_NAME_RE)


class DatCoreDatasetName(ConstrainedStr):
    regex: Optional[Pattern[str]] = re.compile(DATCORE_DATASET_NAME_RE)


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
    name: LocationName
    id: LocationID

    class Config:
        schema_extra = {
            "examples": [{"name": "simcore.s3", "id": 0}, {"name": "datcore", "id": 1}]
        }


FileLocationArray = ListModel[FileLocation]

# /locations/{location_id}/datasets


class DatasetMetaData(BaseModel):
    dataset_id: Union[ProjectID, DatCoreDatasetName]
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
# /locations/{location_id}/files/{file_id}/metadata:
class FileMetaData(BaseModel):
    # Used by frontend
    file_uuid: str = Field(
        description="NOT a unique ID, like (api|uuid)/uuid/file_name or DATCORE folder structure",
    )
    location_id: LocationID = Field(..., description="Storage location")
    project_name: Optional[str] = Field(
        default=None,
        description="optional project name, used by frontend to display path",
    )
    node_name: Optional[str] = Field(
        default=None,
        description="optional node name, used by frontend to display path",
    )
    file_name: str = Field(..., description="Display name for a file")
    file_id: StorageFileID = Field(
        ...,
        description="THIS IS the unique ID for the file. either (api|project_id)/node_id/file_name.ext for S3 and N:package:UUID for datcore",
    )
    created_at: datetime
    last_modified: datetime
    file_size: ByteSize = Field(-1, description="File size in bytes (-1 means invalid)")
    entity_tag: Optional[ETag] = Field(
        default=None,
        description="Entity tag (or ETag), represents a specific version of the file, None if invalid upload or datcore",
    )
    is_soft_link: bool = Field(
        False,
        description="If true, this file is a soft link."
        "i.e. is another entry with the same object_name",
    )

    @validator("location_id", pre=True)
    @classmethod
    def convert_from_str(cls, v):
        if isinstance(v, str):
            return int(v)
        return v

    class Config:
        extra = Extra.forbid
        schema_extra = {
            "examples": [
                # typical S3 entry
                {
                    "created_at": "2020-06-17 12:28:55.705340",
                    "entity_tag": "8711cf258714b2de5498f5a5ef48cc7b",
                    "file_id": "1c46752c-b096-11ea-a3c4-02420a00392e/e603724d-4af1-52a1-b866-0d4b792f8c4a/work.zip",
                    "file_name": "work.zip",
                    "file_size": 17866343,
                    "file_uuid": "1c46752c-b096-11ea-a3c4-02420a00392e/e603724d-4af1-52a1-b866-0d4b792f8c4a/work.zip",
                    "is_soft_link": False,
                    "last_modified": "2020-06-22 13:48:13.398000+00:00",
                    "location_id": 0,
                    "node_name": "JupyterLab Octave",
                    "project_name": "Octave JupyterLab",
                },
                # api entry (not soft link)
                {
                    "created_at": "2020-06-17 12:28:55.705340",
                    "entity_tag": "8711cf258714b2de5498f5a5ef48cc7b",
                    "file_id": "api/7b6b4e3d-39ae-3559-8765-4f815a49984e/tmpf_qatpzx",
                    "file_name": "tmpf_qatpzx",
                    "file_size": 86,
                    "file_uuid": "api/7b6b4e3d-39ae-3559-8765-4f815a49984e/tmpf_qatpzx",
                    "is_soft_link": False,
                    "last_modified": "2020-06-22 13:48:13.398000+00:00",
                    "location_id": 0,
                    "node_name": None,
                    "project_name": None,
                },
                # api entry (soft link)
                {
                    "created_at": "2020-06-17 12:28:55.705340",
                    "entity_tag": "36aa3644f526655a6f557207e4fd25b8",
                    "file_id": "api/6f788ad9-0ad8-3d0d-9722-72f08c24a212/output_data.json",
                    "file_name": "output_data.json",
                    "file_size": 183,
                    "file_uuid": "api/6f788ad9-0ad8-3d0d-9722-72f08c24a212/output_data.json",
                    "is_soft_link": True,
                    "last_modified": "2020-06-22 13:48:13.398000+00:00",
                    "location_id": 0,
                    "node_name": None,
                    "project_name": None,
                },
                # datcore entry
                {
                    "created_at": "2020-05-28T15:48:34.386302+00:00",
                    "entity_tag": None,
                    "file_id": "N:package:ce145b61-7e4f-470b-a113-033653e86d3d",
                    "file_name": "templatetemplate.json",
                    "file_size": 238,
                    "file_uuid": "Kember Cardiac Nerve Model/templatetemplate.json",
                    "is_soft_link": False,
                    "last_modified": "2020-05-28T15:48:37.507387+00:00",
                    "location_id": 1,
                    "node_name": None,
                    "project_name": None,
                },
            ]
        }


class FileMetaDataArray(BaseModel):
    __root__: List[FileMetaData] = []


# /locations/{location_id}/files/{file_id}


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
