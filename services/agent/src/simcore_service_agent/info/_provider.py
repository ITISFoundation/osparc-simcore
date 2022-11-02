import asyncio
import logging

from .._app import Application
from ._constants import HOST, INFO_REQUEST, PORT

logger = logging.getLogger(__name__)


class InfoServerProtocol(asyncio.Protocol):
    def __init__(self, app: Application) -> None:
        self.app = app
        super().__init__()

    def connection_made(self, transport):
        # pylint:disable = attribute-defined-outside-init
        self.transport = transport

    def data_received(self, data):
        message = data.decode()

        if message == INFO_REQUEST:
            message_to_send = f"{self.app.list_running()}\nALL OK"
        else:
            message_to_send = "bad request type"

        self.transport.write(message_to_send.encode())

        self.transport.close()


async def info_exposer(app) -> None:
    loop = asyncio.get_event_loop()

    server = await loop.create_server(lambda: InfoServerProtocol(app), HOST, PORT)
    async with server:
        await server.serve_forever()
