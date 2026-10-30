import logging
from collections.abc import AsyncIterator

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager

from ...core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def configure_socketio(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        external_socketio: socketio.AsyncAioPikaManager | None = None
        try:
            assert app.state.rabbitmq_client  # nosec
            settings: ApplicationSettings = app.state.settings

            # Connect to the as an external process in write-only mode
            # SEE https://python-socketio.readthedocs.io/en/stable/server.html#emitting-from-external-processes
            assert settings.RABBIT_SETTINGS  # nosec
            external_socketio = app.state.external_socketio = socketio.AsyncAioPikaManager(
                url=settings.RABBIT_SETTINGS.dsn, logger=_logger, write_only=True
            )
            yield
        finally:
            if external_socketio is not None:
                await cleanup_socketio_async_pubsub_manager(server_manager=external_socketio)

    app_lifespan.add(_lifespan)
