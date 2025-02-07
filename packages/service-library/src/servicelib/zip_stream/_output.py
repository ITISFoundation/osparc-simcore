from pathlib import Path

import aiofiles

from ._types import FileStream


class DiskStreamWriter:
    def __init__(self, destination_path: Path):
        self.destination_path = destination_path

    async def write_stream(self, stream: FileStream) -> None:
        async with aiofiles.open(self.destination_path, "wb") as f:
            async for chunk in stream:
                await f.write(chunk)
                await f.flush()
