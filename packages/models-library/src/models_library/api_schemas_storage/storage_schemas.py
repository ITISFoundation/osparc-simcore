"""
Models used in storage API:

Specifically services/storage/src/simcore_service_storage/api/v0/openapi.yaml#/components/schemas

IMPORTANT: DO NOT COUPLE these schemas until storage is refactored
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Final, Literal, Self, TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ByteSize,
    ConfigDict,
    Field,
    PositiveInt,
    RootModel,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic.config import JsonDict
from pydantic.networks import AnyUrl

from ..basic_regex import (
    DATCORE_COLLECTION_NAME_RE,
    DATCORE_DATASET_NAME_RE,
    DATCORE_FILE_ID_RE,
    S3_BUCKET_NAME_RE,
)
from ..basic_types import SHA256Str
from ..generics import ListModel
from ..projects import ProjectID
from ..projects_nodes_io import (
    LocationID,
    LocationName,
    NodeID,
    SimcoreS3FileID,
    StorageFileID,
)
from ..users import UserID

ETag: TypeAlias = str

S3BucketName: TypeAlias = Annotated[str, StringConstraints(pattern=S3_BUCKET_NAME_RE)]

DatCoreDatasetName: TypeAlias = Annotated[
    str, StringConstraints(pattern=DATCORE_DATASET_NAME_RE)
]
DatCoreCollectionName: TypeAlias = Annotated[
    str, StringConstraints(pattern=DATCORE_COLLECTION_NAME_RE)
]
DatCorePackageName: TypeAlias = Annotated[
    str, StringConstraints(pattern=DATCORE_FILE_ID_RE)
]


# /
class HealthCheck(BaseModel):
    name: str | None
    status: str | None
    api_version: str | None
    version: str | None


# /locations
class FileLocation(BaseModel):
    name: LocationName
    id: LocationID

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {"name": "simcore.s3", "id": 0},
                    {"name": "datcore", "id": 1},
                ]
            }
        )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra=_update_json_schema_extra,
    )


FileLocationArray: TypeAlias = ListModel[FileLocation]


# /locations/{location_id}/datasets
class DatasetMetaDataGet(BaseModel):
    dataset_id: UUID | DatCoreDatasetName
    display_name: str

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
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
        )

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        json_schema_extra=_update_json_schema_extra,
    )


UNDEFINED_SIZE_TYPE: TypeAlias = Literal[-1]
UNDEFINED_SIZE: UNDEFINED_SIZE_TYPE = -1


class FileMetaDataGetv010(BaseModel):
    file_uuid: str
    location_id: LocationID
    location: LocationName
    bucket_name: str
    object_name: str
    project_id: ProjectID | None
    project_name: str | None
    node_id: NodeID | None
    node_name: str | None
    file_name: str
    user_id: UserID | None
    user_name: str | None

    model_config = ConfigDict(extra="forbid", frozen=True)


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
    file_size: UNDEFINED_SIZE_TYPE | ByteSize = Field(
        default=UNDEFINED_SIZE, description="File size in bytes (-1 means invalid)"
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

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
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
                    # typical directory entry
                    {
                        "created_at": "2020-06-17 12:28:55.705340",
                        "entity_tag": "8711cf258714b2de5498f5a5ef48cc7b",
                        "file_id": "9a759caa-9890-4537-8c26-8edefb7a4d7c/be165f45-ddbf-4911-a04d-bc0b885914ef/workspace",
                        "file_name": "workspace",
                        "file_size": -1,
                        "file_uuid": "9a759caa-9890-4537-8c26-8edefb7a4d7c/be165f45-ddbf-4911-a04d-bc0b885914ef/workspace",
                        "is_soft_link": False,
                        "last_modified": "2020-06-22 13:48:13.398000+00:00",
                        "location_id": 0,
                        "node_name": None,
                        "project_name": None,
                        "is_directory": True,
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
        )

    model_config = ConfigDict(
        extra="ignore",
        from_attributes=True,
        json_schema_extra=_update_json_schema_extra,
    )

    @field_validator("location_id", mode="before")
    @classmethod
    def ensure_location_is_integer(cls, v):
        if v is not None:
            return int(v)
        return v


class FileMetaDataArray(RootModel[list[FileMetaDataGet]]):
    root: list[FileMetaDataGet] = Field(default_factory=list)


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

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    # typical S3 entry
                    {
                        "chunk_size": "10000000",
                        "urls": [
                            "https://s3.amazonaws.com/bucket-name/key-name?AWSAccessKeyId=AKIAIOSFODNN7EXAMPLE&Expires=1698298164&Signature=WObYM%2F%2B4t7O3%2FZS3Kegb%2Bc4%3D",
                        ],
                        "links": {
                            "abort_upload": "https://storage.com:3021/bucket-name/key-name:abort",
                            "complete_upload": "https://storage.com:3021/bucket-name/key-name:complete",
                        },
                    },
                ]
            }
        )

    model_config = ConfigDict(
        extra="forbid", json_schema_extra=_update_json_schema_extra
    )


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
    source: Annotated[dict[str, Any], Field(default_factory=dict)]
    destination: Annotated[dict[str, Any], Field(default_factory=dict)]
    nodes_map: Annotated[dict[NodeID, NodeID], Field(default_factory=dict)]

    @model_validator(mode="after")
    def ensure_consistent_entries(self: Self) -> Self:
        source_node_keys = (NodeID(n) for n in self.source.get("workbench", {}))
        if set(source_node_keys) != set(self.nodes_map.keys()):
            msg = "source project nodes do not fit with nodes_map entries"
            raise ValueError(msg)
        destination_node_keys = (
            NodeID(n) for n in self.destination.get("workbench", {})
        )
        if set(destination_node_keys) != set(self.nodes_map.values()):
            msg = "destination project nodes do not fit with nodes_map values"
            raise ValueError(msg)
        return self


class SoftCopyBody(BaseModel):
    link_id: SimcoreS3FileID


DEFAULT_NUMBER_OF_PATHS_PER_PAGE: Final[int] = 50
MAX_NUMBER_OF_PATHS_PER_PAGE: Final[int] = 1000


class PathMetaDataGet(BaseModel):
    path: Annotated[Path, Field(description="the path to the current path")]
    display_path: Annotated[
        Path,
        Field(
            description="the path to display with UUID replaced (URL Encoded by parts as names may contain '/')"
        ),
    ]

    file_meta_data: Annotated[
        FileMetaDataGet | None,
        Field(description="if filled, this is the file meta data of the s3 object"),
    ] = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    # ls no filter
                    {
                        "path": "f8da77a9-24b9-4eab-aee7-1f0608da1e3e",
                        "display_path": "my amazing project",
                    },
                    # ls f8da77a9-24b9-4eab-aee7-1f0608da1e3e
                    {
                        "path": "f8da77a9-24b9-4eab-aee7-1f0608da1e3e/2f94f80f-633e-4dfa-a983-226b7babe3d7",
                        "display_path": "my amazing project/awesome node",
                    },
                    # ls f8da77a9-24b9-4eab-aee7-1f0608da1e3e/2f94f80f-633e-4dfa-a983-226b7babe3d7
                    {
                        "path": "f8da77a9-24b9-4eab-aee7-1f0608da1e3e/2f94f80f-633e-4dfa-a983-226b7babe3d7/outputs",
                        "display_path": "my amazing project/awesome node/outputs",
                    },
                    # ls f8da77a9-24b9-4eab-aee7-1f0608da1e3e/2f94f80f-633e-4dfa-a983-226b7babe3d7/outputs
                    {
                        "path": "f8da77a9-24b9-4eab-aee7-1f0608da1e3e/2f94f80f-633e-4dfa-a983-226b7babe3d7/outputs/output5",
                        "display_path": "my amazing project/awesome node/outputs/output5",
                    },
                    # ls f8da77a9-24b9-4eab-aee7-1f0608da1e3e/2f94f80f-633e-4dfa-a983-226b7babe3d7/outputs/output_5
                    {
                        "path": f"f8da77a9-24b9-4eab-aee7-1f0608da1e3e/2f94f80f-633e-4dfa-a983-226b7babe3d7/outputs/output5/{FileMetaDataGet.model_json_schema()['examples'][0]['file_name']}",
                        "display_path": f"my amazing project/awesome node/outputs/output5/{FileMetaDataGet.model_json_schema()['examples'][0]['file_name']}",
                        "file_meta_data": FileMetaDataGet.model_json_schema()[
                            "examples"
                        ][0],
                    },
                ]
            }
        )

    model_config = ConfigDict(
        extra="forbid", json_schema_extra=_update_json_schema_extra
    )
