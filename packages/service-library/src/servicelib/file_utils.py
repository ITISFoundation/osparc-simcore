import asyncio
import hashlib
import shutil
from pathlib import Path
from typing import Final, Protocol

# https://docs.python.org/3/library/shutil.html#shutil.rmtree
# https://docs.python.org/3/library/os.html#os.remove
from aiofiles.os import remove
from aiofiles.os import wrap as sync_to_async
from pydantic import ByteSize, parse_obj_as

CHUNK_4KB: Final[ByteSize] = parse_obj_as(ByteSize, "4kb")  # 4K blocks


class AsyncStream(Protocol):
    async def read(self, size: int = -1) -> bytes:
        ...


_shutil_rmtree = sync_to_async(shutil.rmtree)


async def _rm(path: Path, ignore_errors: bool):
    """Removes file or directory"""
    try:
        await remove(path)
    except IsADirectoryError:
        await _shutil_rmtree(path, ignore_errors=ignore_errors)


async def remove_directory(
    path: Path, only_children: bool = False, ignore_errors: bool = False
) -> None:
    """Optional parameter allows to remove all children and keep directory"""
    if only_children:
        await asyncio.gather(*[_rm(child, ignore_errors) for child in path.glob("*")])
    else:
        await _shutil_rmtree(path, ignore_errors=ignore_errors)


async def create_sha256_checksum(
    async_stream: AsyncStream,
    *,
    chunk_size: ByteSize = CHUNK_4KB,
) -> str:
    """
    Usage:
    import aiofiles

    async with aiofiles.open(path, mode="rb") as file:
        sha256check = await create_sha256_checksum(file)

    SEE https://ant.apache.org/manual/Tasks/checksum.html
    WARNING: bandit reports the use of insecure MD2, MD4, MD5, or SHA1 hash function.
    """
    sha256_hash = hashlib.sha256()  # nosec
    sha256check = await _eval_hash_async(async_stream, sha256_hash, chunk_size)
    return sha256check


async def _eval_hash_async(
    async_stream: AsyncStream,
    hasher: "hashlib._Hash",
    chunk_size: ByteSize,
) -> str:
    while chunk := await async_stream.read(chunk_size):
        hasher.update(chunk)
    digest = hasher.hexdigest()
    return f"{digest}"
