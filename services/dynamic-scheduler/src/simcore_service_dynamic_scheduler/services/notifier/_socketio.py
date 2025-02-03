import logging
from collections.abc import AsyncIterator

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager

from ...core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings

    assert app.state.rabbitmq_client  # nosec

    # Connect to the as an external process in write-only mode
    # SEE https://python-socketio.readthedocs.io/en/stable/server.html#emitting-from-external-processes
    assert settings.DYNAMIC_SCHEDULER_RABBITMQ  # nosec
    app.state.external_socketio = socketio.AsyncAioPikaManager(
        url=settings.DYNAMIC_SCHEDULER_RABBITMQ.dsn, logger=_logger, write_only=True
    )

    yield {}

    if external_socketio := getattr(app.state, "external_socketio"):  # noqa: B009
        await cleanup_socketio_async_pubsub_manager(server_manager=external_socketio)
