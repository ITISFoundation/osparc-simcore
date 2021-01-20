import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from ...models.schemas.files import FileUploaded

tmp_prefix = f"{__name__}-"
tmp_dir = Path(tempfile.mkdtemp(prefix=tmp_prefix))

for d in tmp_dir.parent.glob(f"{tmp_prefix}*"):
    if d != tmp_dir and d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


@dataclass
class FilesFaker:
    base_dir: Path
    files: List[Tuple[FileUploaded, Path]]

    async def get(self, checksum: str):
        for m, p in self.files:
            if m.hash == checksum:
                return m, p
        raise KeyError()

    async def save(self, metadata, file_handler):
        self.base_dir.mkdir(exist_ok=True)

        path = self.base_dir / f"{metadata.hash[:5]}-{metadata.filename}"
        await file_handler.seek(0)
        data = await file_handler.read()
        path.write_bytes(data)

        if not any(m.hash == metadata.hash for m, _ in self.files):
            self.files.append((metadata, path))


the_fake_impl = FilesFaker(base_dir=tmp_dir, files=[])
