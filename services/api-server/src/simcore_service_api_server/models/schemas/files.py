from mimetypes import guess_type
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import quote as _quote
from urllib.parse import unquote as _unquote
from uuid import UUID, uuid3

import aiofiles
from fastapi import UploadFile
from models_library.api_schemas_storage import ETag
from models_library.basic_types import SHA256Str
from models_library.projects_nodes_io import StorageFileID
from pydantic import (
    AnyUrl,
    BaseModel,
    ByteSize,
    ConstrainedStr,
    Field,
    parse_obj_as,
    validator,
)
from servicelib.file_utils import create_sha256_checksum

_NAMESPACE_FILEID_KEY = UUID("aa154444-d22d-4290-bb15-df37dba87865")


class FileName(ConstrainedStr):
    strip_whitespace = True


class ClientFile(BaseModel):
    """Represents a file stored on the client side"""

    filename: FileName = Field(..., description="File name")
    filesize: ByteSize = Field(..., description="File size in bytes")
    sha256_checksum: SHA256Str = Field(..., description="SHA256 checksum")


class File(BaseModel):
    """Represents a file stored on the server side i.e. a unique reference to a file in the cloud."""

    # WARNING: from pydantic import File as FileParam
    # NOTE: see https://ant.apache.org/manual/Tasks/checksum.html

    id: UUID = Field(..., description="Resource identifier")  # noqa: A003

    filename: str = Field(..., description="Name of the file with extension")
    content_type: str | None = Field(
        default=None, description="Guess of type content [EXPERIMENTAL]"
    )
    sha256_checksum: SHA256Str | None = Field(
        default=None,
        description="SHA256 hash of the file's content",
        alias="checksum",  # alias for backwards compatibility
    )
    e_tag: ETag | None = Field(default=None, description="S3 entity tag")

    class Config:
        allow_population_by_field_name = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # complete
                {
                    "id": "f0e1fb11-208d-3ed2-b5ef-cab7a7398f78",
                    "filename": "Architecture-of-Scalable-Distributed-ETL-System-whitepaper.pdf",
                    "content_type": "application/pdf",
                    "checksum": "de47d0e1229aa2dfb80097389094eadd-1",
                },
                # minimum
                {
                    "id": "f0e1fb11-208d-3ed2-b5ef-cab7a7398f78",
                    "filename": "whitepaper.pdf",
                },
            ]
        }

    @validator("content_type", always=True, pre=True)
    @classmethod
    def guess_content_type(cls, v, values):
        if v is None:
            filename = values.get("filename")
            if filename:
                mime_content_type, _ = guess_type(filename, strict=False)
                return mime_content_type
        return v

    @classmethod
    async def create_from_path(cls, path: Path) -> "File":
        async with aiofiles.open(path, mode="rb") as file:
            sha256check = await create_sha256_checksum(file)

        return cls(
            id=cls.create_id(sha256check, path.name),
            filename=path.name,
            checksum=SHA256Str(sha256check),
        )

    @classmethod
    async def create_from_file_link(cls, s3_object_path: str, e_tag: str) -> "File":
        filename = Path(s3_object_path).name
        return cls(
            id=cls.create_id(e_tag, filename),
            filename=filename,
            e_tag=e_tag,
        )

    @classmethod
    async def create_from_uploaded(
        cls, file: UploadFile, *, file_size=None, created_at=None
    ) -> "File":
        sha256check = await create_sha256_checksum(file)
        # WARNING: UploadFile wraps a stream and wil checkt its cursor position: file.file.tell() != 0
        # WARNING: await file.seek(0) might introduce race condition if not done carefuly

        return cls(
            id=cls.create_id(sha256check or file_size, file.filename, created_at),
            filename=file.filename or "Undefined",
            content_type=file.content_type,
            checksum=SHA256Str(sha256check),
        )

    @classmethod
    async def create_from_client_file(
        cls,
        client_file: ClientFile,
        created_at: str,
    ) -> "File":
        return cls(
            id=cls.create_id(client_file.filesize, client_file.filename, created_at),
            filename=client_file.filename,
            checksum=client_file.sha256_checksum,
        )

    @classmethod
    async def create_from_quoted_storage_id(cls, quoted_storage_id: str) -> "File":
        storage_file_id: StorageFileID = parse_obj_as(
            StorageFileID, _unquote(quoted_storage_id)
        )
        _, fid, fname = Path(storage_file_id).parts
        return cls(id=UUID(fid), filename=fname, checksum=None)

    @classmethod
    def create_id(cls, *keys) -> UUID:
        return uuid3(_NAMESPACE_FILEID_KEY, ":".join(map(str, keys)))

    @property
    def storage_file_id(self) -> StorageFileID:
        """Get the StorageFileId associated with this file"""
        return parse_obj_as(StorageFileID, f"api/{self.id}/{self.filename}")

    @property
    def quoted_storage_file_id(self) -> str:
        """Quoted version of the StorageFileId"""
        return _quote(self.storage_file_id, safe="")


class UploadLinks(BaseModel):
    abort_upload: str
    complete_upload: str


class FileUploadData(BaseModel):
    chunk_size: ByteSize
    urls: list[AnyUrl]
    links: UploadLinks


class ClientFileUploadData(BaseModel):
    file_id: UUID = Field(..., description="The file resource id")
    upload_schema: FileUploadData = Field(..., description="Schema for uploading file")
