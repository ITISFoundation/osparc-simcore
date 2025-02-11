from pathlib import Path

import aiofiles
from servicelib.zip_stream._file_like import FileLikeFileStreamReader

from ._types import FileStream


class DiskStreamWriter:
    def __init__(self, destination_path: Path):
        self.destination_path = destination_path

    async def write_from_stream(self, stream: FileStream) -> None:
        async with aiofiles.open(self.destination_path, "wb") as f:
            async for chunk in stream:
                await f.write(chunk)
                await f.flush()

    async def write_from_file_like(
        self, file_like_reader: FileLikeFileStreamReader
    ) -> None:
        async with aiofiles.open(self.destination_path, "wb") as f:
            while True:
                chunk = await file_like_reader.read(100)
                if not chunk:
                    break

                await f.write(chunk)
                await f.flush()
