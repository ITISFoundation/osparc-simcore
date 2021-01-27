from mimetypes import guess_type
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid3

import aiofiles
from fastapi import UploadFile
from pydantic import BaseModel, Field

from ...utils.hash import create_md5_checksum

NAMESPACE_FILEID_KEY = UUID("aa154444-d22d-4290-bb15-df37dba87865")


class FileMetadata(BaseModel):
    """ Describes a file stored on the server side """

    file_id: UUID = Field(
        None, description="File unique identifier built upon its name and checksum"
    )

    filename: str = Field(..., description="File with extenson")
    content_type: Optional[str] = None

    # SEE https://ant.apache.org/manual/Tasks/checksum.html
    checksum: str = Field(..., description="MD5 hash of the file's content")

    @classmethod
    async def create_from_path(cls, path: Path) -> "FileMetadata":
        async with aiofiles.open(path, mode="rb") as file:
            md5check = await create_md5_checksum(file)

        mime_content_type, _ = guess_type(path.name)
        return cls(
            file_id=cls.create_id(md5check, path.name),
            filename=path.name,
            content_type=mime_content_type,
            checksum=md5check,
        )

    @classmethod
    async def create_from_uploaded(cls, file: UploadFile) -> "FileMetadata":

        md5check = await create_md5_checksum(file)
        # WARNING: UploadFile wraps a stream and wil checkt its cursor position: file.file.tell() != 0
        # WARNING: await file.seek(0) might introduce race condition if not done carefuly

        return cls(
            file_id=cls.create_id(md5check, file.filename),
            filename=file.filename,
            content_type=file.content_type,
            checksum=md5check,
        )

    @classmethod
    def create_id(cls, checksum, filename) -> UUID:
        return uuid3(NAMESPACE_FILEID_KEY, f"{checksum}:{filename}")
