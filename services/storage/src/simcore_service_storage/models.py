import datetime
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, NamedTuple, TypeAlias
from uuid import UUID

import arrow
from aws_library.s3 import UploadID
from aws_library.s3._models import S3DirectoryMetaData, S3MetaData
from models_library.api_schemas_storage.storage_schemas import (
    UNDEFINED_SIZE,
    UNDEFINED_SIZE_TYPE,
    DatasetMetaDataGet,
    ETag,
    FileMetaDataGet,
    LinkType,
    PathMetaDataGet,
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
    NonNegativeInt,
    PlainSerializer,
    TypeAdapter,
    field_validator,
    model_validator,
    validate_call,
)


class DatasetMetaData(DatasetMetaDataGet): ...


def is_uuid(value: str) -> bool:
    try:
        UUID(str(value))
    except ValueError:
        return False
    return True


class FileMetaDataAtDB(BaseModel):
    location_id: Annotated[
        LocationID, PlainSerializer(lambda x: f"{x}", return_type=str)
    ]
    location: LocationName
    bucket_name: S3BucketName
    object_name: SimcoreS3FileID
    project_id: Annotated[
        ProjectID | None,
        PlainSerializer(
            lambda x: f"{x}" if x is not None else None, return_type=str | None
        ),
    ] = None
    node_id: Annotated[
        NodeID | None,
        PlainSerializer(
            lambda x: f"{x}" if x is not None else None, return_type=str | None
        ),
    ] = None
    user_id: Annotated[UserID, PlainSerializer(lambda x: f"{x}", return_type=str)]
    created_at: Annotated[datetime.datetime, PlainSerializer(lambda x: x.isoformat())]
    file_id: SimcoreS3FileID
    file_size: UNDEFINED_SIZE_TYPE | ByteSize
    last_modified: Annotated[
        datetime.datetime, PlainSerializer(lambda x: x.isoformat())
    ]
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

    def update_display_fields(self, id_name_mapping: dict[str, str]) -> None:
        if self.project_id:
            # NOTE: this is disabled because the project_name is defined in FileMetaDataGet
            # pylint: disable=attribute-defined-outside-init
            self.project_name = id_name_mapping.get(f"{self.project_id}")
        if self.node_id:
            # NOTE: this is disabled because the node_name is defined in FileMetaDataGet
            # pylint: disable=attribute-defined-outside-init
            self.node_name = id_name_mapping.get(f"{self.node_id}")

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

    @classmethod
    def from_db_model(cls, x: FileMetaDataAtDB) -> "FileMetaData":
        return cls.model_validate(
            x.model_dump()
            | {"file_uuid": x.file_id, "file_name": x.file_id.split("/")[-1]}
        )

    @classmethod
    def from_s3_object_in_dir(
        cls, x: S3MetaData, dir_fmd: "FileMetaData"
    ) -> "FileMetaData":
        return dir_fmd.model_copy(
            update={
                "object_name": x.object_key,
                "file_id": x.object_key,
                "file_size": x.size,
                "entity_tag": x.e_tag,
                "sha256_checksum": x.sha256_checksum,
                "is_directory": False,
                "created_at": x.last_modified,
                "last_modified": x.last_modified,
            }
        )


@dataclass
class UploadLinks:
    urls: list[AnyUrl]
    chunk_size: ByteSize


class StorageQueryParamsBase(BaseModel):
    user_id: UserID
    model_config = ConfigDict(populate_by_name=True)


class ListPathsQueryParams(StorageQueryParamsBase):
    file_filter: Path | None = None


class FilesMetadataDatasetQueryParams(StorageQueryParamsBase):
    expand_dirs: bool = True


class FileMetadataListQueryParams(StorageQueryParamsBase):
    project_id: ProjectID | None = None
    uuid_filter: str = ""
    expand_dirs: bool = True


class SyncMetadataQueryParams(BaseModel):
    dry_run: bool = False
    fire_and_forget: bool = False


class SyncMetadataResponse(BaseModel):
    removed: list[StorageFileID]
    fire_and_forget: bool
    dry_run: bool


class FileDownloadQueryParams(StorageQueryParamsBase):
    link_type: LinkType = LinkType.PRESIGNED


class FileDownloadResponse(BaseModel):
    link: AnyUrl


class FileUploadQueryParams(StorageQueryParamsBase):
    link_type: LinkType = LinkType.PRESIGNED
    file_size: ByteSize | None = None  # NOTE: in old legacy services this might happen
    is_directory: bool = False
    sha256_checksum: SHA256Str | None = None

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


class FileUploadResponseV1(BaseModel):
    link: AnyUrl


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
        return v  # type: ignore[unreachable]


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
        return v  # type: ignore[unreachable]


class UserOrProjectFilter(NamedTuple):
    user_id: UserID | None  # = None disables filter
    project_ids: list[ProjectID]


@dataclass(frozen=True)
class AccessRights:
    read: bool
    write: bool
    delete: bool

    @classmethod
    def all(cls) -> "AccessRights":
        return cls(read=True, write=True, delete=True)

    @classmethod
    def none(cls) -> "AccessRights":
        return cls(read=False, write=False, delete=False)


TotalNumber: TypeAlias = NonNegativeInt
GenericCursor: TypeAlias = str | bytes


class PathMetaData(BaseModel):
    path: Path
    display_path: Annotated[
        Path,
        Field(
            description="Path with names instead of IDs (URL Encoded by parts as names may contain '/')"
        ),
    ]
    location_id: LocationID
    location: LocationName
    bucket_name: str

    project_id: ProjectID | None
    node_id: NodeID | None
    user_id: UserID | None
    created_at: datetime.datetime
    last_modified: datetime.datetime

    file_meta_data: FileMetaData | None

    def update_display_fields(self, id_name_mapping: dict[str, str]) -> None:
        display_path = f"{self.path}"
        for old, new in id_name_mapping.items():
            display_path = display_path.replace(old, urllib.parse.quote(new, safe=""))
        self.display_path = Path(display_path)

        if self.file_meta_data:
            self.file_meta_data.update_display_fields(id_name_mapping)

    @classmethod
    def from_s3_object_in_dir(
        cls, s3_object: S3MetaData | S3DirectoryMetaData, dir_fmd: FileMetaData
    ) -> "PathMetaData":
        return cls(
            path=s3_object.as_path(),
            display_path=s3_object.as_path(),
            location_id=dir_fmd.location_id,
            location=dir_fmd.location,
            bucket_name=dir_fmd.bucket_name,
            user_id=dir_fmd.user_id,
            project_id=dir_fmd.project_id,
            node_id=dir_fmd.node_id,
            created_at=dir_fmd.created_at,
            last_modified=dir_fmd.last_modified,
            file_meta_data=(
                None
                if isinstance(s3_object, S3DirectoryMetaData)
                else FileMetaData.from_s3_object_in_dir(s3_object, dir_fmd)
            ),
        )

    def to_api_model(self) -> PathMetaDataGet:
        return PathMetaDataGet.model_construct(
            path=self.path,
            display_path=self.display_path,
            file_meta_data=self.file_meta_data,
        )
