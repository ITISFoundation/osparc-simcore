# mypy: disable-error-code=truthy-function
import logging
from collections.abc import AsyncIterator

from aiohttp import web
from common_library.json_serialization import JsonNamespace
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager
from socketio import AsyncAioPikaManager, AsyncServer  # type: ignore[import-untyped]

from ..rabbitmq_settings import get_plugin_settings as get_rabbitmq_settings
from . import _handlers
from ._utils import (
    CLIENT_SOCKET_SERVER_APPKEY,
    get_socket_server,
    register_socketio_handlers,
)

_logger = logging.getLogger(__name__)


async def _socketio_server_cleanup_ctx(app: web.Application) -> AsyncIterator[None]:
    # SEE https://github.com/miguelgrinberg/python-socketio/blob/v4.6.1/docs/server.rst#aiohttp
    server_manager = AsyncAioPikaManager(url=get_rabbitmq_settings(app).dsn)
    sio_server = AsyncServer(
        async_mode="aiohttp",
        logger=True,
        engineio_logger=True,
        client_manager=server_manager,
        json=JsonNamespace,
    )
    sio_server.attach(app)

    app[CLIENT_SOCKET_SERVER_APPKEY] = sio_server

    register_socketio_handlers(app, _handlers)

    yield

    await cleanup_socketio_async_pubsub_manager(server_manager)


def setup_socketio_server(app: web.Application) -> None:
    app.cleanup_ctx.append(_socketio_server_cleanup_ctx)


assert get_socket_server  # nosec

__all__: tuple[str, ...] = (
    "get_socket_server",
    "setup_socketio_server",
)
