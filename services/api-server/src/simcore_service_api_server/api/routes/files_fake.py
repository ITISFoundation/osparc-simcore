from pathlib import Path
from typing import List, Tuple

from ...models.schemas.files import FileUploaded


class FAKE:
    base_dir = Path("./ignore")
    files: List[Tuple[FileUploaded, Path]] = []

    @classmethod
    async def get(cls, hash):
        for m, p in cls.files:
            if m.hash == hash:
                return m, p
        raise KeyError()

    @classmethod
    async def save(cls, metadata, file):
        cls.base_dir.mkdir(exist_ok=True)

        path = cls.base_dir / f"{metadata.hash[:5]}-{metadata.filename}"
        await file.seek(0)
        data = await file.read()
        path.write_bytes(data)

        if not any(m.hash == metadata.hash for m, _ in cls.files):
            cls.files.append((metadata, path))
