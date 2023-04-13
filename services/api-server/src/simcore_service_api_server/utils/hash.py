"""
    Helpers functions around https://docs.python.org/3/library/hashlib.html?highlight=hashlib

"""
import hashlib

CHUNK_4KB = 4 * 1024  # 4K blocks


async def create_md5_checksum(async_stream, *, chunk_size=CHUNK_4KB) -> str:
    """
    Usage:
    import aiofiles

    async with aiofiles.open(path, mode="rb") as file:
        md5check = await create_md5_checksum(file)

    SEE https://ant.apache.org/manual/Tasks/checksum.html
    WARNING: bandit reports the use of insecure MD2, MD4, MD5, or SHA1 hash function.
    """
    md5_hash = hashlib.md5()  # nosec
    return await _eval_hash_async(async_stream, md5_hash, chunk_size)


async def _eval_hash_async(async_stream, hasher, chunk_size) -> str:
    more_chunk = True
    while more_chunk:
        chunk = await async_stream.read(chunk_size)
        more_chunk = len(chunk) == chunk_size

        hasher.update(chunk)
    digest = hasher.hexdigest()
    return f"{digest}"
