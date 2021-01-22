"""
    Fakes the implementation of the files API section by
    replacing the storage service by local storage of the
    files uploaded to the system.

    The real implementation should instead use storage API
    and get upload/download links to S3 services and avoid
    the data traffic to go via the API server

    This module should be used ONLY when AppSettings.fake_server_enabled==True
"""


import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from uuid import UUID

import aiofiles
from fastapi import UploadFile

from ...models.schemas.files import FileMetadata
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
    files: Dict[UUID, FileMetadata]

    def list_meta(self) -> List[FileMetadata]:
        return list(self.files.values())

    def get_storage_path(self, metadata) -> Path:
        if not self.storage_dir.exists():
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        return self.storage_dir / f"{metadata.checksum}"

    async def save(self, uploaded_file: UploadFile) -> FileMetadata:

        metadata = await FileMetadata.create_from_uploaded(uploaded_file)
        await uploaded_file.seek(0)  # NOTE: create_from_uploaded moved cursor

        path = self.get_storage_path(metadata)

        if not path.exists():
            assert metadata.file_id not in self.files  # nosec

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

        self.files[metadata.file_id] = metadata
        return metadata


clean_storage_dirs()

the_fake_impl = StorageFaker(storage_dir=STORAGE_DIR, files={})
