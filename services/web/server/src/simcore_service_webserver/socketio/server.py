import asyncio
import logging
from typing import AsyncIterator

from aiohttp import web
from socketio import AsyncServer

APP_CLIENT_SOCKET_SERVER_KEY = f"{__name__}.socketio_socketio"
APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY = f"{__name__}.socketio_handlers"

log = logging.getLogger(__name__)


def get_socket_server(app: web.Application) -> AsyncServer:
    return app[APP_CLIENT_SOCKET_SERVER_KEY]


async def _socketio_server_cleanup_ctx(_app: web.Application) -> AsyncIterator[None]:
    yield
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
            ]
        ):
            task.cancel()
            cancelled_tasks.append(task)
    await asyncio.gather(*cancelled_tasks, return_exceptions=True)


def setup_socketio_server(app: web.Application):
    if app.get(APP_CLIENT_SOCKET_SERVER_KEY) is None:
        # SEE https://github.com/miguelgrinberg/python-socketio/blob/v4.6.1/docs/server.rst#aiohttp
        # TODO: ujson to speed up?
        # TODO: client_manager= to socketio.AsyncRedisManager/AsyncAioPikaManager for horizontal scaling (shared sessions)
        sio = AsyncServer(async_mode="aiohttp", logger=log, engineio_logger=False)
        sio.attach(app)

        app[APP_CLIENT_SOCKET_SERVER_KEY] = sio
        app.cleanup_ctx.append(_socketio_server_cleanup_ctx)

    return get_socket_server(app)
