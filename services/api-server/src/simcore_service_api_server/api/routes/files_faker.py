import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from ...models.schemas.files import FileUploaded

# Directory used to save files uploaded to
# the fake server
STORAGE_DIR = Path(tempfile.mkdtemp(prefix=f"{__name__}-"))


def prune_other_storage_dirs():
    for d in STORAGE_DIR.parent.glob(f"{__name__}*"):
        if d != STORAGE_DIR and d.is_dir():
            print("Removing dire")
            shutil.rmtree(d, ignore_errors=True)


@dataclass
class FilesFaker:
    storage_dir: Path
    files: List[Tuple[FileUploaded, Path]]

    # TODO: normal class
    # load/save to storage_dir
    #

    async def get(self, checksum: str):
        for m, p in self.files:
            if m.hash == checksum:
                return m, p
        raise KeyError()

    async def save(self, metadata, file_handler):

        path = self.storage_dir / f"{metadata.hash[:5]}-{metadata.filename}"
        await file_handler.seek(0)
        data = await file_handler.read()
        path.write_bytes(data)

        if not any(m.hash == metadata.hash for m, _ in self.files):
            self.files.append((metadata, path))


prune_other_storage_dirs()

the_fake_impl = FilesFaker(storage_dir=STORAGE_DIR, files=[])
