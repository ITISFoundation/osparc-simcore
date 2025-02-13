from pathlib import Path

import aiofiles

from ._file_like import FileLikeFileStreamReader
from ._models import DataStream


class DiskStreamWriter:
    def __init__(self, destination_path: Path):
        self.destination_path = destination_path

    async def write_from_stream(self, stream: DataStream) -> None:
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
