"""
    Models used in storage API:

    Specifically services/storage/src/simcore_service_storage/api/v0/openapi.yaml#/components/schemas

    IMPORTANT: DO NOT COUPLE these schemas until storage is refactored
"""

import re
from datetime import datetime
from enum import Enum
from re import Pattern
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ByteSize,
    ConfigDict,
    ConstrainedStr,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)
from pydantic.networks import AnyUrl

from .basic_regex import DATCORE_DATASET_NAME_RE, S3_BUCKET_NAME_RE
from .basic_types import SHA256Str
from .generics import ListModel
from .projects_nodes_io import (
    LocationID,
    LocationName,
    NodeID,
    SimcoreS3FileID,
    StorageFileID,
)

ETag = str


class S3BucketName(ConstrainedStr):
    regex: Pattern[str] | None = re.compile(S3_BUCKET_NAME_RE)


class DatCoreDatasetName(ConstrainedStr):
    regex: Pattern[str] | None = re.compile(DATCORE_DATASET_NAME_RE)


# /
class HealthCheck(BaseModel):
    name: str | None = None
    status: str | None = None
    api_version: str | None = None
    version: str | None = None


# /locations
class FileLocation(BaseModel):
    name: LocationName
    id: LocationID
    model_config = ConfigDict(extra="forbid")


FileLocationArray = ListModel[FileLocation]


# /locations/{location_id}/datasets
class DatasetMetaDataGet(BaseModel):
    dataset_id: UUID | DatCoreDatasetName
    display_name: str
    model_config = ConfigDict(extra="forbid", from_attributes=True)


# /locations/{location_id}/files/metadata:
# /locations/{location_id}/files/{file_id}/metadata:
class FileMetaDataGet(BaseModel):
    # Used by frontend
    file_uuid: str = Field(
        description="NOT a unique ID, like (api|uuid)/uuid/file_name or DATCORE folder structure",
    )
    location_id: LocationID = Field(..., description="Storage location")
    project_name: str | None = Field(
        default=None,
        description="optional project name, used by frontend to display path",
    )
    node_name: str | None = Field(
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
    file_size: ByteSize | int = Field(
        default=-1, description="File size in bytes (-1 means invalid)"
    )
    entity_tag: ETag | None = Field(
        default=None,
        description="Entity tag (or ETag), represents a specific version of the file, None if invalid upload or datcore",
    )
    is_soft_link: bool = Field(
        default=False,
        description="If true, this file is a soft link."
        "i.e. is another entry with the same object_name",
    )
    is_directory: bool = Field(default=False, description="if True this is a directory")
    sha256_checksum: SHA256Str | None = Field(
        default=None,
        description="SHA256 message digest of the file content. Main purpose: cheap lookup.",
    )

    @field_validator("location_id", mode="before")
    @classmethod
    @classmethod
    def ensure_location_is_integer(cls, v):
        if v is not None:
            return int(v)
        return v

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class FileMetaDataArray(BaseModel):
    __root__: list[FileMetaDataGet] = []


# /locations/{location_id}/files/{file_id}


class LinkType(str, Enum):
    PRESIGNED = "PRESIGNED"
    S3 = "S3"


class PresignedLink(BaseModel):
    link: AnyUrl


class FileUploadLinks(BaseModel):
    abort_upload: AnyUrl
    complete_upload: AnyUrl


class FileUploadSchema(BaseModel):
    chunk_size: ByteSize
    urls: list[AnyUrl]
    links: FileUploadLinks


class TableSynchronisation(BaseModel):
    dry_run: bool | None = None
    fire_and_forget: bool | None = None
    removed: list[str]


# /locations/{location_id}/files/{file_id}:complete
class UploadedPart(BaseModel):
    number: PositiveInt
    e_tag: ETag


class FileUploadCompletionBody(BaseModel):
    parts: list[UploadedPart]

    @field_validator("parts")
    @classmethod
    @classmethod
    def ensure_sorted(cls, value: list[UploadedPart]) -> list[UploadedPart]:
        return sorted(value, key=lambda uploaded_part: uploaded_part.number)


class FileUploadCompleteLinks(BaseModel):
    state: AnyUrl


class FileUploadCompleteResponse(BaseModel):
    links: FileUploadCompleteLinks


# /locations/{location_id}/files/{file_id}:complete/futures/{future_id}
class FileUploadCompleteState(Enum):
    OK = "ok"
    NOK = "nok"


class FileUploadCompleteFutureResponse(BaseModel):
    state: FileUploadCompleteState
    e_tag: ETag | None = Field(default=None)


# /simcore-s3/


class FoldersBody(BaseModel):
    source: dict[str, Any] = Field(default_factory=dict)
    destination: dict[str, Any] = Field(default_factory=dict)
    nodes_map: dict[NodeID, NodeID] = Field(default_factory=dict)

    @model_validator()
    @classmethod
    @classmethod
    def ensure_consistent_entries(cls, values):
        source_node_keys = (NodeID(n) for n in values["source"].get("workbench", {}))
        if set(source_node_keys) != set(values["nodes_map"].keys()):
            msg = "source project nodes do not fit with nodes_map entries"
            raise ValueError(msg)
        destination_node_keys = (
            NodeID(n) for n in values["destination"].get("workbench", {})
        )
        if set(destination_node_keys) != set(values["nodes_map"].values()):
            msg = "destination project nodes do not fit with nodes_map values"
            raise ValueError(msg)
        return values


class SoftCopyBody(BaseModel):
    link_id: SimcoreS3FileID
