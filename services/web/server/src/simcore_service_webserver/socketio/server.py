import asyncio
import logging
from typing import AsyncIterator

from aiohttp import web
from socketio import AsyncAioPikaManager, AsyncServer

from ..rabbitmq_settings import get_plugin_settings as get_rabbitmq_settings
from . import _handlers
from ._utils import APP_CLIENT_SOCKET_SERVER_KEY, register_socketio_handlers

_logger = logging.getLogger(__name__)


async def _socketio_server_cleanup_ctx(app: web.Application) -> AsyncIterator[None]:
    # SEE https://github.com/miguelgrinberg/python-socketio/blob/v4.6.1/docs/server.rst#aiohttp
    server_manager = AsyncAioPikaManager(
        url=get_rabbitmq_settings(app).dsn, logger=_logger
    )
    sio_server = AsyncServer(
        async_mode="aiohttp",
        logger=_logger,  # type: ignore
        engineio_logger=False,
        client_manager=server_manager,
    )
    sio_server.attach(app)

    app[APP_CLIENT_SOCKET_SERVER_KEY] = sio_server

    register_socketio_handlers(app, _handlers)
    yield
    # cast(AsyncPubSubManager, server_manager).thread.cancel()
    # NOTE: this is ugly. It seems though that python-enginio does not
    # cleanup its background tasks properly.
    # https://github.com/miguelgrinberg/python-socketio/discussions/1092
    current_tasks = asyncio.tasks.all_tasks()
    cancelled_tasks = []
    for task in current_tasks:
        coro = task.get_coro()
        if any(
            coro_name in coro.__qualname__  # type: ignore
            for coro_name in [
                "AsyncServer._service_task",
                "AsyncSocket.schedule_ping",
                "AsyncPubSubManager._thread",
            ]
        ):
            task.cancel()
            cancelled_tasks.append(task)
    await asyncio.gather(*cancelled_tasks, return_exceptions=True)


def setup_socketio_server(app: web.Application) -> None:
    app.cleanup_ctx.append(_socketio_server_cleanup_ctx)


__all__: tuple[str, ...] = (
    "get_socket_server",
    "setup_socketio_server",
)
