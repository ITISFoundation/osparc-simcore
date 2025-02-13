from models_library.data_streams import DataStream


class FileLikeDataStreamReader:
    def __init__(self, data_stream: DataStream):
        self._data_stream = data_stream
        self._buffer = bytearray()
        self._async_iterator = self._get_iterator()

    async def _get_iterator(self):
        async for chunk in self._data_stream:
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
