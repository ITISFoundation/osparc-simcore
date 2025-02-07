from pathlib import Path

import aiofiles

from ._constants import DEFAULT_CHUNK_SIZE
from ._types import FileStream


class DiskStreamReader:
    def __init__(self, file_path: Path, *, chunk_size=DEFAULT_CHUNK_SIZE):
        self.file_path = file_path
        self.chunk_size = chunk_size

    async def get_stream(self) -> FileStream:
        async with aiofiles.open(self.file_path, "rb") as f:
            while True:
                chunk = await f.read(self.chunk_size)
                if not chunk:
                    break
                yield chunk
