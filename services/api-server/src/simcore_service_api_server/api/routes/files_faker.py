"""
    Fakes the implementation of the files API section by
    replacing the storage service by local storage of the
    files uploaded to the system.

    The real implementation should instead use storage API
    and get upload/download links to S3 services and avoid
    the data traffic to go via the API server

    This module should be used ONLY when AppSettings.fake_server_enabled==True
"""


import hashlib
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from fastapi import UploadFile

from ...models.schemas.files import FileUploaded

logger = logging.getLogger(__name__)

# Directory used to save files uploaded to
# the fake server
STORAGE_DIR = Path(tempfile.mkdtemp(prefix=f"{__name__}-"))


def clean_storage_dirs():
    for d in STORAGE_DIR.parent.glob(f"{__name__}*"):
        if d != STORAGE_DIR and d.is_dir():
            logger.debug("Cleaning up storage %s", d)
            shutil.rmtree(d, ignore_errors=True)


async def eval_sha256_hash(file: UploadFile):
    # TODO: adaptive chunks depending on file size
    # SEE: https://stackoverflow.com/questions/17731660/hashlib-optimal-size-of-chunks-to-be-used-in-md5-update

    CHUNK_BYTES = 4 * 1024  # 4K blocks

    # TODO: put a limit in size to upload!
    sha256_hash = hashlib.sha256()

    await file.seek(0)
    while True:
        chunk = await file.read(CHUNK_BYTES)
        if not chunk:
            break
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


@dataclass
class StorageFaker:
    storage_dir: Path
    files: Dict[Path, FileUploaded]

    def list_meta(self) -> List[FileUploaded]:
        return list(self.files.values())

    async def get(self, filehash: str) -> Tuple[FileUploaded, Path]:
        for p, m in self.files.items():
            if m.hash == filehash:
                return m, p
        raise KeyError()

    async def save(self, file_handler) -> FileUploaded:
        filehash = await eval_sha256_hash(file_handler)

        # key
        path = self.storage_dir / f"{filehash}-{file_handler.filename}"

        if not path.exists():
            # creates metadata value
            metadata = FileUploaded(
                filename=file_handler.filename,
                content_type=file_handler.content_type,
                hash=filehash,
            )
            # store
            logger.info("Saving %s  -> %s", metadata, path.name)
            await file_handler.seek(0)
            data = await file_handler.read()
            path.write_bytes(data)

            # ok, now register
            self.files[path] = metadata

        return self.files[path]


clean_storage_dirs()

the_fake_impl = StorageFaker(storage_dir=STORAGE_DIR, files={})
