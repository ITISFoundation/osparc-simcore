"""
    Fakes the implementation of the files API section by
    replacing the storage service by local storage of the
    files uploaded to the system.

    The real implementation should instead use storage API
    and get upload/download links to S3 services and avoid
    the data traffic to go via the API server

    This module should be used ONLY when AppSettings.dev_feature_enabled==True
"""


import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from uuid import UUID

import aiofiles
from fastapi import UploadFile, status
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse

from ...models.schemas.files import File
from ...utils.hash import CHUNK_4KB

logger = logging.getLogger(__name__)

# Directory used to save files uploaded to
# the fake server
STORAGE_DIR = Path(tempfile.mkdtemp(prefix=f"{__name__}-"))


def clean_storage_dirs():
    for d in STORAGE_DIR.parent.glob(f"{__name__}*"):
        if d != STORAGE_DIR and d.is_dir():
            logger.debug("Cleaning up storage %s", d)
            shutil.rmtree(d, ignore_errors=True)


@dataclass
class StorageFaker:
    """
    Emulates a Single Instance Storage
    Real one will be S3 and will work with upload/download links

    SEE https://en.wikipedia.org/wiki/Data_deduplication
    """

    storage_dir: Path
    files: Dict[UUID, File]

    def list_meta(self) -> List[File]:
        return list(self.files.values())

    def get_storage_path(self, metadata) -> Path:
        if not self.storage_dir.exists():
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        return self.storage_dir / f"{metadata.checksum}"

    async def save(self, uploaded_file: UploadFile) -> File:

        metadata = await File.create_from_uploaded(uploaded_file)
        await uploaded_file.seek(0)  # NOTE: create_from_uploaded moved cursor

        path = self.get_storage_path(metadata)

        if not path.exists():
            assert metadata.id not in self.files, str(metadata)  # nosec

            # store
            logger.info("Saving %s  -> %s", metadata, path.name)
            chunk_size: int = CHUNK_4KB

            async with aiofiles.open(path, mode="wb") as store_file:
                more_data = True
                while more_data:
                    chunk = await uploaded_file.read(chunk_size)
                    more_data = len(chunk) == chunk_size
                    await store_file.write(chunk)

        assert path.exists()  # nosec

        self.files[metadata.id] = metadata
        return metadata


clean_storage_dirs()

the_fake_impl = StorageFaker(storage_dir=STORAGE_DIR, files={})


# /files API fake implementations

# GET /files
async def list_files_fake_implementation():
    return the_fake_impl.list_meta()


# GET /files/{file_id}
async def get_file_fake_implementation(
    file_id: UUID,
):
    try:
        return the_fake_impl.files[file_id]
    except KeyError as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"File with identifier {file_id} not found",
        ) from err


# POST /files:upload
async def upload_file_fake_implementation(file: UploadFile):
    metadata = await the_fake_impl.save(file)
    return metadata


# POST /files:download
async def download_file_fake_implementation(file_id: UUID):
    try:
        metadata = the_fake_impl.files[file_id]
        file_path = the_fake_impl.get_storage_path(metadata)

        return FileResponse(
            str(file_path),
            media_type=metadata.content_type,
            filename=metadata.filename,
        )
    except KeyError as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"File with identifier {file_id} not found",
        ) from err
