from pathlib import Path

import aiofiles
from models_library.bytes_iters import BytesIter, DataSize

from ._constants import DEFAULT_READ_CHUNK_SIZE
from ._models import BytesStreamer


class DiskStreamReader:
    def __init__(self, file_path: Path, *, chunk_size=DEFAULT_READ_CHUNK_SIZE):
        self.file_path = file_path
        self.chunk_size = chunk_size

    def get_bytes_streamer(self) -> BytesStreamer:
        async def _() -> BytesIter:
            async with aiofiles.open(self.file_path, "rb") as f:
                while True:
                    chunk = await f.read(self.chunk_size)
                    if not chunk:
                        break

                    yield chunk

        return BytesStreamer(DataSize(self.file_path.stat().st_size), _)
