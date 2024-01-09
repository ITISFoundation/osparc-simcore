import logging

import socketio
from fastapi import FastAPI
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager

from ....core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def setup_socketio(app: FastAPI):
    settings: ApplicationSettings = app.state.settings

    async def _on_startup() -> None:
        assert app.state.rabbitmq_client  # nosec

        # Connect to the as an external process in write-only mode
        # SEE https://python-socketio.readthedocs.io/en/stable/server.html#emitting-from-external-processes
        app.state.external_socketio = socketio.AsyncAioPikaManager(
            url=settings.DYNAMIC_SCHEDULER_RABBITMQ.dsn, logger=_logger, write_only=True
        )

    async def _on_shutdown() -> None:
        if app.state.external_socketio:
            await cleanup_socketio_async_pubsub_manager(
                server_manager=app.state.external_socketio
            )

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
