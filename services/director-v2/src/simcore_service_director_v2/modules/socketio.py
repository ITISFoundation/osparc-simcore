import logging

import socketio
from fastapi import FastAPI
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager

from ..core.settings import AppSettings

_logger = logging.getLogger(__name__)


def setup(app: FastAPI):
    settings: AppSettings = app.state.settings

    async def _on_startup() -> None:
        assert app.state.rabbitmq_client  # nosec

        # Connect to the as an external process in write-only mode
        # SEE https://python-socketio.readthedocs.io/en/stable/server.html#emitting-from-external-processes
        app.state.external_socketio = socketio.AsyncAioPikaManager(
            url=settings.DIRECTOR_V2_RABBITMQ.dsn,
            logger=_logger,
            write_only=True,
        )

    async def _on_shutdown() -> None:
        if external_socketio := getattr(app.state, "external_socketio"):  # noqa: B009
            await cleanup_socketio_async_pubsub_manager(
                server_manager=external_socketio
            )

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
