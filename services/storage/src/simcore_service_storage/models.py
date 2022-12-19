import datetime
import urllib.parse
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from models_library.api_schemas_storage import (
    DatasetMetaDataGet,
    ETag,
    FileMetaDataGet,
    LinkType,
    S3BucketName,
)
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
    validate_arguments,
    validator,
)

UploadID = str


class DatasetMetaData(DatasetMetaDataGet):
    ...


def is_uuid(value: str) -> bool:
    try:
        UUID(str(value))
    except ValueError:
        return False
    else:
        return True


class FileMetaDataAtDB(BaseModel):
    location_id: LocationID
    location: LocationName
    bucket_name: S3BucketName
    object_name: SimcoreS3FileID
    project_id: Optional[ProjectID] = None
    node_id: Optional[NodeID] = None
    user_id: UserID
    created_at: datetime.datetime
    file_id: SimcoreS3FileID
    file_size: ByteSize
    last_modified: datetime.datetime
    entity_tag: Optional[ETag] = None
    is_soft_link: bool
    upload_id: Optional[UploadID] = None
    upload_expires_at: Optional[datetime.datetime] = None

    class Config:
        orm_mode = True
        extra = Extra.forbid


class FileMetaData(FileMetaDataGet):
    upload_id: Optional[UploadID] = None
    upload_expires_at: Optional[datetime.datetime] = None

    location: LocationName
    bucket_name: str
    object_name: str
    project_id: Optional[ProjectID]
    node_id: Optional[NodeID]
    user_id: Optional[UserID]

    @classmethod
    @validate_arguments
    def from_simcore_node(
        cls,
        user_id: UserID,
        file_id: SimcoreS3FileID,
        bucket: S3BucketName,
        location_id: LocationID,
        location_name: LocationName,
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
            "file_size": ByteSize(-1),
            "entity_tag": None,
            "is_soft_link": False,
            "upload_id": None,
            "upload_expires_at": None,
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


class FilesMetadataQueryParams(StorageQueryParamsBase):
    uuid_filter: str = ""


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
    file_size: Optional[ByteSize]

    @validator("link_type", pre=True)
    @classmethod
    def convert_from_lower_case(cls, v):
        if v is not None:
            return f"{v}".upper()
        return v


class DeleteFolderQueryParams(StorageQueryParamsBase):
    node_id: Optional[NodeID] = None


class SearchFilesQueryParams(StorageQueryParamsBase):
    startswith: str = ""


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
