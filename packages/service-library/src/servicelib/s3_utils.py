from typing import Protocol

from models_library.bytes_iters import BytesIter


class FileLikeReader(Protocol):
    """minimal interface for upload from file objects to S3"""

    async def read(self, size: int) -> bytes:
        ...


class FileLikeBytesIterReader(FileLikeReader):
    def __init__(self, bytes_iter: BytesIter):
        self._bytes_iter = bytes_iter
        self._buffer = bytearray()
        self._async_iterator = self._get_iterator()

    async def _get_iterator(self):
        async for chunk in self._bytes_iter:
            yield chunk

    async def read(self, size: int) -> bytes:
        while len(self._buffer) < size:
            try:
                chunk = await anext(self._async_iterator)
                self._buffer.extend(chunk)
            except StopAsyncIteration:
                break  # End of file

        result, self._buffer = self._buffer[:size], self._buffer[size:]
        return bytes(result)
