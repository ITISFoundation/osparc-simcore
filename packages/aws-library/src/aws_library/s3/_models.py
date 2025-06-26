import datetime
from pathlib import Path
from typing import Annotated, TypeAlias, cast

from models_library.api_schemas_storage.storage_schemas import ETag
from models_library.basic_types import SHA256Str
from pydantic import AnyUrl, BaseModel, ByteSize, Field
from types_aiobotocore_s3.type_defs import HeadObjectOutputTypeDef, ObjectTypeDef

S3ObjectKey: TypeAlias = str
S3ObjectPrefix: TypeAlias = Path
UploadID: TypeAlias = str
PathCursor: TypeAlias = str


class S3MetaData(BaseModel, frozen=True):
    object_key: S3ObjectKey
    last_modified: datetime.datetime
    e_tag: ETag
    sha256_checksum: SHA256Str | None
    size: ByteSize

    @staticmethod
    def from_botocore_head_object(
        object_key: S3ObjectKey, obj: HeadObjectOutputTypeDef
    ) -> "S3MetaData":
        return S3MetaData(
            object_key=object_key,
            last_modified=obj["LastModified"],
            e_tag=obj["ETag"].strip('"'),
            sha256_checksum=obj.get("ChecksumSHA256"),
            size=ByteSize(obj["ContentLength"]),
        )

    @staticmethod
    def from_botocore_list_objects(
        obj: ObjectTypeDef,
    ) -> "S3MetaData":
        assert "Key" in obj  # nosec
        assert "LastModified" in obj  # nosec
        assert "ETag" in obj  # nosec
        assert "Size" in obj  # nosec
        return S3MetaData(
            object_key=obj["Key"],
            last_modified=obj["LastModified"],
            e_tag=obj["ETag"].strip('"'),
            sha256_checksum=cast(SHA256Str | None, obj.get("ChecksumSHA256")),
            size=ByteSize(obj["Size"]),
        )

    def as_path(self) -> Path:
        return Path(self.object_key)


class S3DirectoryMetaData(BaseModel, frozen=True):
    prefix: S3ObjectPrefix
    size: Annotated[
        ByteSize | None,
        Field(description="Size of the directory if computed, None if unknown"),
    ]

    def as_path(self) -> Path:
        return self.prefix


class MultiPartUploadLinks(BaseModel):
    upload_id: UploadID
    chunk_size: ByteSize
    urls: list[AnyUrl]
