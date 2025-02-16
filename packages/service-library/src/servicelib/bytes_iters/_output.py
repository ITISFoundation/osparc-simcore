from pathlib import Path

import aiofiles
from models_library.bytes_iters import BytesIter

from ..s3_utils import FileLikeBytesIterReader


class DiskStreamWriter:
    def __init__(self, destination_path: Path):
        self.destination_path = destination_path

    async def write_from_bytes_iter(self, stream: BytesIter) -> None:
        async with aiofiles.open(self.destination_path, "wb") as f:
            async for chunk in stream:
                await f.write(chunk)
                await f.flush()

    async def write_from_file_like(
        self, file_like_reader: FileLikeBytesIterReader
    ) -> None:
        async with aiofiles.open(self.destination_path, "wb") as f:
            while True:
                chunk = await file_like_reader.read(100)
                if not chunk:
                    break

                await f.write(chunk)
                await f.flush()
