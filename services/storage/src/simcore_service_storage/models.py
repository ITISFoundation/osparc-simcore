import datetime
import urllib.parse
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from models_library.api_schemas_storage import (
    DatasetMetaDataGet,
    ETag,
    FileMetaDataGet,
    LinkType,
    S3BucketName,
)
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import (
    LocationID,
    LocationName,
    SimcoreS3FileID,
    StorageFileID,
)
from models_library.users import UserID
from pydantic import (
    AnyUrl,
    BaseModel,
    ByteSize,
    Extra,
    parse_obj_as,
    root_validator,
    validate_arguments,
    validator,
)

UNDEFINED_SIZE: Final[ByteSize] = parse_obj_as(ByteSize, -1)

UploadID = str


class DatasetMetaData(DatasetMetaDataGet):
    ...


def is_uuid(value: str) -> bool:
    try:
        UUID(str(value))
    except ValueError:
        return False
    return True


class FileMetaDataAtDB(BaseModel):
    location_id: LocationID
    location: LocationName
    bucket_name: S3BucketName
    object_name: SimcoreS3FileID
    project_id: ProjectID | None = None
    node_id: NodeID | None = None
    user_id: UserID
    created_at: datetime.datetime
    file_id: SimcoreS3FileID
    file_size: ByteSize
    last_modified: datetime.datetime
    entity_tag: ETag | None = None
    is_soft_link: bool
    upload_id: UploadID | None = None
    upload_expires_at: datetime.datetime | None = None
    is_directory: bool
    sha256_checksum: SHA256Str | None = None

    class Config:
        orm_mode = True
        extra = Extra.forbid


class FileMetaData(FileMetaDataGet):
    upload_id: UploadID | None = None
    upload_expires_at: datetime.datetime | None = None

    location: LocationName
    bucket_name: str
    object_name: str
    project_id: ProjectID | None
    node_id: NodeID | None
    user_id: UserID | None
    sha256_checksum: SHA256Str | None

    @classmethod
    @validate_arguments
    def from_simcore_node(
        cls,
        user_id: UserID,
        file_id: SimcoreS3FileID,
        bucket: S3BucketName,
        location_id: LocationID,
        location_name: LocationName,
        sha256_checksum: SHA256Str | None,
        **file_meta_data_kwargs,
    ):
        parts = file_id.split("/")
        now = datetime.datetime.utcnow()
        fmd_kwargs = {
            "file_uuid": file_id,
            "location_id": location_id,
            "location": location_name,
            "bucket_name": bucket,
            "object_name": file_id,
            "file_name": parts[-1],
            "user_id": user_id,
            "project_id": parse_obj_as(ProjectID, parts[0])
            if is_uuid(parts[0])
            else None,
            "node_id": parse_obj_as(NodeID, parts[1]) if is_uuid(parts[1]) else None,
            "file_id": file_id,
            "created_at": now,
            "last_modified": now,
            "file_size": UNDEFINED_SIZE,
            "entity_tag": None,
            "is_soft_link": False,
            "upload_id": None,
            "upload_expires_at": None,
            "sha256_checksum": sha256_checksum,
            "is_directory": False,
        }
        fmd_kwargs.update(**file_meta_data_kwargs)
        return cls.parse_obj(fmd_kwargs)


@dataclass
class UploadLinks:
    urls: list[AnyUrl]
    chunk_size: ByteSize


class MultiPartUploadLinks(BaseModel):
    upload_id: UploadID
    chunk_size: ByteSize
    urls: list[AnyUrl]


class StorageQueryParamsBase(BaseModel):
    user_id: UserID

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid


class FilesMetadataDatasetQueryParams(StorageQueryParamsBase):
    expand_dirs: bool = True


class FilesMetadataQueryParams(StorageQueryParamsBase):
    uuid_filter: str = ""
    expand_dirs: bool = True


class SyncMetadataQueryParams(BaseModel):
    dry_run: bool = False
    fire_and_forget: bool = False


class FileDownloadQueryParams(StorageQueryParamsBase):
    link_type: LinkType = LinkType.PRESIGNED

    @validator("link_type", pre=True)
    @classmethod
    def convert_from_lower_case(cls, v):
        if v is not None:
            return f"{v}".upper()
        return v


class FileUploadQueryParams(StorageQueryParamsBase):
    link_type: LinkType = LinkType.PRESIGNED
    file_size: ByteSize | None
    is_directory: bool = False
    sha256_checksum: SHA256Str | None = None

    @validator("link_type", pre=True)
    @classmethod
    def convert_from_lower_case(cls, v):
        if v is not None:
            return f"{v}".upper()
        return v

    @root_validator()
    @classmethod
    def when_directory_force_link_type_and_file_size(cls, values):
        if values["is_directory"] is True:
            # sets directory size by default to undefined
            values["file_size"] = UNDEFINED_SIZE
            # only 1 link will be returned manged by the uploader
            values["link_type"] = LinkType.S3
        return values


class DeleteFolderQueryParams(StorageQueryParamsBase):
    node_id: NodeID | None = None


class SearchFilesQueryParams(StorageQueryParamsBase):
    startswith: str = ""
    sha256_checksum: SHA256Str | None = None
    access_right: Literal["read", "write"] = "read"


class LocationPathParams(BaseModel):
    location_id: LocationID

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid


class FilesMetadataDatasetPathParams(LocationPathParams):
    dataset_id: str


class FilePathParams(LocationPathParams):
    file_id: StorageFileID

    @validator("file_id", pre=True)
    @classmethod
    def unquote(cls, v):
        if v is not None:
            return urllib.parse.unquote(f"{v}")
        return v


class FilePathIsUploadCompletedParams(FilePathParams):
    future_id: str


class SimcoreS3FoldersParams(BaseModel):
    folder_id: str


class CopyAsSoftLinkParams(BaseModel):
    file_id: StorageFileID

    @validator("file_id", pre=True)
    @classmethod
    def unquote(cls, v):
        if v is not None:
            return urllib.parse.unquote(f"{v}")
        return v


__all__ = (
    "ETag",
    "FileMetaData",
    "FileMetaDataAtDB",
    "S3BucketName",
    "SimcoreS3FileID",
    "StorageFileID",
    "UploadID",
    "UploadLinks",
)
