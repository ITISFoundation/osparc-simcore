"""
    Helpers functions around https://docs.python.org/3/library/hashlib.html?highlight=hashlib

"""
import hashlib

from models_library.basic_types import SHA256Str

CHUNK_4KB = 4 * 1024  # 4K blocks


async def create_sha256_checksum(async_stream, *, chunk_size=CHUNK_4KB) -> SHA256Str:
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
    return SHA256Str(sha256check)


async def _eval_hash_async(async_stream, hasher, chunk_size) -> str:
    more_chunk = True
    while more_chunk:
        chunk = await async_stream.read(chunk_size)
        more_chunk = len(chunk) == chunk_size

        hasher.update(chunk)
    digest = hasher.hexdigest()
    return f"{digest}"
