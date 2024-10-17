import asyncio
import hashlib
import shutil
from contextlib import contextmanager
from logging import Logger
from pathlib import Path
from typing import Final, Iterator, Protocol

# https://docs.python.org/3/library/shutil.html#shutil.rmtree
# https://docs.python.org/3/library/os.html#os.remove
from aiofiles.os import remove
from aiofiles.os import wrap as sync_to_async
from pydantic import ByteSize, TypeAdapter

CHUNK_4KB: Final[ByteSize] = TypeAdapter(ByteSize).validate_python("4kb")  # 4K blocks


class AsyncStream(Protocol):
    async def read(self, size: int = -1) -> bytes:
        ...


_shutil_rmtree = sync_to_async(shutil.rmtree)


async def _rm(path: Path, *, ignore_errors: bool):
    """Removes file or directory"""
    try:
        await remove(path)
    except IsADirectoryError:
        await _shutil_rmtree(path, ignore_errors=ignore_errors)


async def remove_directory(
    path: Path, *, only_children: bool = False, ignore_errors: bool = False
) -> None:
    """Optional parameter allows to remove all children and keep directory"""
    if only_children:
        await asyncio.gather(
            *[_rm(child, ignore_errors=ignore_errors) for child in path.glob("*")]
        )
    else:
        await _shutil_rmtree(path, ignore_errors=ignore_errors)


async def create_sha256_checksum(
    async_stream: AsyncStream, *, chunk_size: ByteSize = CHUNK_4KB
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
    return await _eval_hash_async(async_stream, sha256_hash, chunk_size)


async def _eval_hash_async(
    async_stream: AsyncStream,
    hasher: "hashlib._Hash",
    chunk_size: ByteSize,
) -> str:
    while chunk := await async_stream.read(chunk_size):
        hasher.update(chunk)
    digest = hasher.hexdigest()
    return f"{digest}"


def _get_file_properties(path: Path) -> tuple[float, int]:
    stats = path.stat()
    return stats.st_mtime, stats.st_size


def _get_directory_snapshot(path: Path) -> dict[str, tuple[float, int]]:
    return {
        f"{p.relative_to(path)}": _get_file_properties(p)
        for p in path.rglob("*")
        if p.is_file()
    }


@contextmanager
def log_directory_changes(path: Path, logger: Logger, log_level: int) -> Iterator[None]:
    before: dict[str, tuple[float, int]] = _get_directory_snapshot(path)
    yield
    after: dict[str, tuple[float, int]] = _get_directory_snapshot(path)

    after_keys: set[str] = set(after.keys())
    before_keys: set[str] = set(before.keys())
    common_keys = before_keys & after_keys

    added_elements = after_keys - before_keys
    removed_elements = before_keys - after_keys
    content_changed_elements = {x for x in common_keys if before[x] != after[x]}

    if added_elements or removed_elements or content_changed_elements:
        logger.log(log_level, "File changes in path: '%s'", f"{path}")
    if added_elements:
        logger.log(
            log_level,
            "Files added:\n%s",
            "\n".join([f"+ {x}" for x in sorted(added_elements)]),
        )
    if removed_elements:
        logger.log(
            log_level,
            "Files removed:\n%s",
            "\n".join([f"- {x}" for x in sorted(removed_elements)]),
        )
    if content_changed_elements:
        logger.log(
            log_level,
            "File content changed:\n%s",
            "\n".join([f"* {x}" for x in sorted(content_changed_elements)]),
        )
