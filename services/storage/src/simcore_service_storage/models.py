import datetime
import urllib.parse
from dataclasses import dataclass
from typing import Any, Literal, NamedTuple
from uuid import UUID

import arrow
from aws_library.s3 import UploadID
from models_library.api_schemas_storage import (
    UNDEFINED_SIZE,
    UNDEFINED_SIZE_TYPE,
    DatasetMetaDataGet,
    ETag,
    FileMetaDataGet,
    LinkType,
    S3BucketName,
)
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes_io import (
    LocationID,
    LocationName,
    NodeID,
    SimcoreS3FileID,
    StorageFileID,
)
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
)
from models_library.users import UserID
from models_library.utils.common_validators import empty_str_to_none_pre_validator
from pydantic import (
    AnyUrl,
    BaseModel,
    ByteSize,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
    validate_call,
)


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
    file_size: UNDEFINED_SIZE_TYPE | ByteSize
    last_modified: datetime.datetime
    entity_tag: ETag | None = None
    is_soft_link: bool
    upload_id: UploadID | None = None
    upload_expires_at: datetime.datetime | None = None
    is_directory: bool
    sha256_checksum: SHA256Str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


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
    @validate_call
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
        now = arrow.utcnow().datetime
        fmd_kwargs = {
            "file_uuid": file_id,
            "location_id": location_id,
            "location": location_name,
            "bucket_name": bucket,
            "object_name": file_id,
            "file_name": parts[-1],
            "user_id": user_id,
            "project_id": (
                TypeAdapter(ProjectID).validate_python(parts[0])
                if is_uuid(parts[0])
                else None
            ),
            "node_id": (
                TypeAdapter(NodeID).validate_python(parts[1])
                if is_uuid(parts[1])
                else None
            ),
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
        return cls.model_validate(fmd_kwargs)


@dataclass
class UploadLinks:
    urls: list[AnyUrl]
    chunk_size: ByteSize


class StorageQueryParamsBase(BaseModel):
    user_id: UserID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class FilesMetadataDatasetQueryParams(StorageQueryParamsBase):
    expand_dirs: bool = True


class FilesMetadataQueryParams(StorageQueryParamsBase):
    project_id: ProjectID | None = None
    uuid_filter: str = ""
    expand_dirs: bool = True


class SyncMetadataQueryParams(BaseModel):
    dry_run: bool = False
    fire_and_forget: bool = False


class FileDownloadQueryParams(StorageQueryParamsBase):
    link_type: LinkType = LinkType.PRESIGNED

    @field_validator("link_type", mode="before")
    @classmethod
    def convert_from_lower_case(cls, v: str) -> str:
        if v is not None:
            return f"{v}".upper()
        return v


class FileUploadQueryParams(StorageQueryParamsBase):
    link_type: LinkType = LinkType.PRESIGNED
    file_size: ByteSize | None = None  # NOTE: in old legacy services this might happen
    is_directory: bool = False
    sha256_checksum: SHA256Str | None = None

    @field_validator("link_type", mode="before")
    @classmethod
    def convert_from_lower_case(cls, v: str) -> str:
        if v is not None:
            return f"{v}".upper()
        return v

    @model_validator(mode="before")
    @classmethod
    def when_directory_force_link_type_and_file_size(cls, data: Any) -> Any:
        assert isinstance(data, dict)

        if TypeAdapter(bool).validate_python(data.get("is_directory", "false")):
            # sets directory size by default to undefined
            if int(data.get("file_size", -1)) < 0:
                data["file_size"] = None
            # only 1 link will be returned manged by the uploader
            data["link_type"] = LinkType.S3.value
        return data

    @property
    def is_v1_upload(self) -> bool:
        """This returns True if the query params are missing the file_size query parameter, which was the case in the legacy services that have an old version of simcore-sdk
        v1 rationale:
        - client calls this handler, which returns a single link (either direct S3 or presigned) to the S3 backend
        - client uploads the file
        - storage relies on lazy update to find if the file is finished uploaded (when client calls get_file_meta_data, or if the dsm_cleaner goes over it after the upload time is expired)
        """
        return self.file_size is None and self.is_directory is False


class DeleteFolderQueryParams(StorageQueryParamsBase):
    node_id: NodeID | None = None


class SearchFilesQueryParams(StorageQueryParamsBase):
    startswith: str | None = None
    sha256_checksum: SHA256Str | None = None
    kind: Literal["owned"]
    limit: int = Field(
        default=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        ge=1,
        le=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
        description="Page size limit",
    )
    offset: int = Field(default=0, ge=0, description="Page offset")

    _empty_is_none = field_validator("startswith", mode="before")(
        empty_str_to_none_pre_validator
    )


class LocationPathParams(BaseModel):
    location_id: LocationID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class FilesMetadataDatasetPathParams(LocationPathParams):
    dataset_id: str


class FilePathParams(LocationPathParams):
    file_id: StorageFileID

    @field_validator("file_id", mode="before")
    @classmethod
    def unquote(cls, v: str) -> str:
        if v is not None:
            return urllib.parse.unquote(f"{v}")
        return v


class FilePathIsUploadCompletedParams(FilePathParams):
    future_id: str


class SimcoreS3FoldersParams(BaseModel):
    folder_id: str


class CopyAsSoftLinkParams(BaseModel):
    file_id: StorageFileID

    @field_validator("file_id", mode="before")
    @classmethod
    def unquote(cls, v: str) -> str:
        if v is not None:
            return urllib.parse.unquote(f"{v}")
        return v


class UserOrProjectFilter(NamedTuple):
    user_id: UserID | None  # = None disables filter
    project_ids: list[ProjectID]


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
