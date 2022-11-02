import asyncio

from ._constants import HOST, INFO_REQUEST, PORT

_8_BYTES = 8 * 1024


async def _async_request_info() -> str:
    reader, writer = await asyncio.open_connection(HOST, PORT)

    writer.write(INFO_REQUEST.encode())
    await writer.drain()

    data = await reader.read(_8_BYTES)
    writer.close()
    await writer.wait_closed()

    return data.decode()


def request_info() -> str:
    return asyncio.run(_async_request_info())
