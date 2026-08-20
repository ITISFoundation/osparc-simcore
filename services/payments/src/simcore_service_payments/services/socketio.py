import logging
from collections.abc import AsyncIterator

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager
from settings_library.rabbit import RabbitSettings

from .rabbitmq import get_rabbitmq_settings

_logger = logging.getLogger(__name__)


def configure_socketio(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _socketio_lifespan(app: FastAPI) -> AsyncIterator[State]:
        settings: RabbitSettings = get_rabbitmq_settings(app)
        assert app.state.rabbitmq_client  # nosec

        # Connect to the as an external process in write-only mode
        # SEE https://python-socketio.readthedocs.io/en/stable/server.html#emitting-from-external-processes
        app.state.external_socketio = socketio.AsyncAioPikaManager(url=settings.dsn, logger=_logger, write_only=True)
        try:
            yield {}
        finally:
            if app.state.external_socketio:
                await cleanup_socketio_async_pubsub_manager(server_manager=app.state.external_socketio)

    app_lifespan.add(_socketio_lifespan)
