import datetime
from dataclasses import dataclass
from typing import TypeAlias

from models_library.api_schemas_storage.rest.storage_schemas import ETag
from models_library.basic_types import SHA256Str
from pydantic import AnyUrl, BaseModel, ByteSize
from types_aiobotocore_s3.type_defs import HeadObjectOutputTypeDef, ObjectTypeDef

S3ObjectKey: TypeAlias = str
UploadID: TypeAlias = str


@dataclass(frozen=True, slots=True, kw_only=True)
class S3MetaData:
    object_key: S3ObjectKey
    last_modified: datetime.datetime
    e_tag: ETag
    sha256_checksum: SHA256Str | None
    size: int

    @staticmethod
    def from_botocore_head_object(
        object_key: S3ObjectKey, obj: HeadObjectOutputTypeDef
    ) -> "S3MetaData":
        return S3MetaData(
            object_key=object_key,
            last_modified=obj["LastModified"],
            e_tag=obj["ETag"].strip('"'),
            sha256_checksum=(
                SHA256Str(obj.get("ChecksumSHA256"))
                if obj.get("ChecksumSHA256")
                else None
            ),
            size=obj["ContentLength"],
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
            sha256_checksum=(
                SHA256Str(obj.get("ChecksumSHA256"))
                if obj.get("ChecksumSHA256")
                else None
            ),
            size=obj["Size"],
        )


@dataclass(frozen=True)
class S3DirectoryMetaData:
    size: int


class MultiPartUploadLinks(BaseModel):
    upload_id: UploadID
    chunk_size: ByteSize
    urls: list[AnyUrl]
