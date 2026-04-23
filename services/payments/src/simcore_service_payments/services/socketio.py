import logging

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager
from settings_library.rabbit import RabbitSettings

from .rabbitmq import get_rabbitmq_settings

_logger = logging.getLogger(__name__)


def setup_socketio(app: FastAPI):
    settings: RabbitSettings = get_rabbitmq_settings(app)

    async def _on_startup() -> None:
        assert app.state.rabbitmq_client  # nosec

        # Connect to the as an external process in write-only mode
        # SEE https://python-socketio.readthedocs.io/en/stable/server.html#emitting-from-external-processes
        app.state.external_socketio = socketio.AsyncAioPikaManager(url=settings.dsn, logger=_logger, write_only=True)

    async def _on_shutdown() -> None:
        if app.state.external_socketio:
            await cleanup_socketio_async_pubsub_manager(server_manager=app.state.external_socketio)

    app.router.on_startup.append(_on_startup)
    app.router.on_shutdown.append(_on_shutdown)
