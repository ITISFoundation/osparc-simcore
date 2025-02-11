from pathlib import Path

import aiofiles

from ..progress_bar import ProgressBarData
from ._constants import DEFAULT_READ_CHUNK_SIZE
from ._types import FileSize, FileStream, StreamData


class DiskStreamReader:
    def __init__(self, file_path: Path, *, chunk_size=DEFAULT_READ_CHUNK_SIZE):
        self.file_path = file_path
        self.chunk_size = chunk_size

    def get_stream_data(self) -> StreamData:
        async def _(progress_bar: ProgressBarData) -> FileStream:
            async with aiofiles.open(self.file_path, "rb") as f:
                while True:
                    chunk = await f.read(self.chunk_size)
                    if not chunk:
                        break

                    await progress_bar.update(len(chunk))
                    yield chunk

        return FileSize(self.file_path.stat().st_size), _
