from pathlib import Path

import aiofiles
from models_library.data_streams import BytesIter, DataSize

from ._constants import DEFAULT_READ_CHUNK_SIZE
from ._models import StreamData


class DiskStreamReader:
    def __init__(self, file_path: Path, *, chunk_size=DEFAULT_READ_CHUNK_SIZE):
        self.file_path = file_path
        self.chunk_size = chunk_size

    def get_stream_data(self) -> StreamData:
        async def _() -> BytesIter:
            async with aiofiles.open(self.file_path, "rb") as f:
                while True:
                    chunk = await f.read(self.chunk_size)
                    if not chunk:
                        break

                    yield chunk

        return StreamData(DataSize(self.file_path.stat().st_size), _)
