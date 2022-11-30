import logging

from aiohttp import web
from socketio import AsyncServer

APP_CLIENT_SOCKET_SERVER_KEY = f"{__name__}.socketio_socketio"
APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY = f"{__name__}.socketio_handlers"

log = logging.getLogger(__name__)


def get_socket_server(app: web.Application) -> AsyncServer:
    return app[APP_CLIENT_SOCKET_SERVER_KEY]


def setup_socketio_server(app: web.Application):
    if app.get(APP_CLIENT_SOCKET_SERVER_KEY) is None:
        # SEE https://github.com/miguelgrinberg/python-socketio/blob/v4.6.1/docs/server.rst#aiohttp
        # TODO: ujson to speed up?
        # TODO: client_manager= to socketio.AsyncRedisManager/AsyncAioPikaManager for horizontal scaling (shared sessions)
        sio = AsyncServer(
            async_mode="aiohttp",
            logger=log,  # type: ignore
            engineio_logger=False,
        )
        sio.attach(app)

        app[APP_CLIENT_SOCKET_SERVER_KEY] = sio

    return get_socket_server(app)
