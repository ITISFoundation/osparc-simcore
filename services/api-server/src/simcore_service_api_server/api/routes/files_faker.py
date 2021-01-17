import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple

from ...models.schemas.files import FileUploaded

tmp_prefix = f"{__name__}-"
tmp_dir = Path(tempfile.mkdtemp(prefix=tmp_prefix))

for d in tmp_dir.parent.glob(f"{tmp_prefix}*"):
    if d != tmp_dir and d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


class FAKE:
    base_dir = tmp_dir
    files: List[Tuple[FileUploaded, Path]] = []

    @classmethod
    async def get(cls, checksum: str):
        for m, p in cls.files:
            if m.hash == checksum:
                return m, p
        raise KeyError()

    @classmethod
    async def save(cls, metadata, file_handler):
        cls.base_dir.mkdir(exist_ok=True)

        path = cls.base_dir / f"{metadata.hash[:5]}-{metadata.filename}"
        await file_handler.seek(0)
        data = await file_handler.read()
        path.write_bytes(data)

        if not any(m.hash == metadata.hash for m, _ in cls.files):
            cls.files.append((metadata, path))
