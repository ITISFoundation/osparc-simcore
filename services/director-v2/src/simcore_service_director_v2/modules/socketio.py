import logging
from collections.abc import AsyncIterator

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager

from ..core.settings import AppSettings

_logger = logging.getLogger(__name__)


def configure_socketio(app_lifespan: LifespanManager) -> None:
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings: AppSettings = app.state.settings
        assert app.state.rabbitmq_client  # nosec

        # Connect to the as an external process in write-only mode
        # SEE https://python-socketio.readthedocs.io/en/stable/server.html#emitting-from-external-processes
        external_socketio = socketio.AsyncAioPikaManager(
            url=settings.DIRECTOR_V2_RABBITMQ.dsn,
            logger=_logger,
            write_only=True,
        )
        app.state.external_socketio = external_socketio
        try:
            yield
        finally:
            await cleanup_socketio_async_pubsub_manager(server_manager=external_socketio)

    app_lifespan.add(_lifespan)
