import asyncio
from pathlib import Path
from typing import IO, AsyncGenerator

import aiofiles


async def file_object_chunk_reader(
    file_object: IO, *, offset: int, total_bytes_to_read: int, chunk_size: int
) -> AsyncGenerator[bytes, None]:
    await asyncio.get_event_loop().run_in_executor(None, file_object.seek, offset)
    num_read_bytes = 0
    while chunk := await asyncio.get_event_loop().run_in_executor(
        None, file_object.read, min(chunk_size, total_bytes_to_read - num_read_bytes)
    ):
        num_read_bytes += len(chunk)
        yield chunk


async def file_chunk_reader(
    file: Path, *, offset: int, total_bytes_to_read: int, chunk_size: int
) -> AsyncGenerator[bytes, None]:
    async with aiofiles.open(file, "rb") as f:
        await f.seek(offset)
        num_read_bytes = 0
        while chunk := await f.read(
            min(chunk_size, total_bytes_to_read - num_read_bytes)
        ):
            num_read_bytes += len(chunk)
            yield chunk
