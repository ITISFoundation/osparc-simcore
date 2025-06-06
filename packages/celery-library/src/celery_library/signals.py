import asyncio
import datetime
import logging
import threading
from collections.abc import Callable
from typing import Final

from asgi_lifespan import LifespanManager
from celery import Celery  # type: ignore[import-untyped]
from celery.worker.worker import WorkController  # type: ignore[import-untyped]
from fastapi import FastAPI
from servicelib.logging_utils import log_context
from settings_library.celery import CelerySettings

from . import set_event_loop
from .common import create_task_manager
from .utils import (
    get_fastapi_app,
    set_fastapi_app,
    set_task_manager,
)

_logger = logging.getLogger(__name__)

_SHUTDOWN_TIMEOUT: Final[float] = datetime.timedelta(seconds=10).total_seconds()
_STARTUP_TIMEOUT: Final[float] = datetime.timedelta(minutes=1).total_seconds()


def on_worker_init(
    app_factory: Callable[[], FastAPI],
    celery_settings: CelerySettings,
    sender: WorkController,
    **_kwargs,
) -> None:
    startup_complete_event = threading.Event()

    def _init(startup_complete_event: threading.Event) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        shutdown_event = asyncio.Event()

        fastapi_app = app_factory()
        assert isinstance(fastapi_app, FastAPI)  # nosec

        async def setup_task_manager():
            assert sender.app  # nosec
            assert isinstance(sender.app, Celery)  # nosec
            set_task_manager(
                sender.app,
                create_task_manager(
                    sender.app,
                    celery_settings,
                ),
            )

        async def fastapi_lifespan(
            startup_complete_event: threading.Event, shutdown_event: asyncio.Event
        ) -> None:
            async with LifespanManager(
                fastapi_app,
                startup_timeout=_STARTUP_TIMEOUT,
                shutdown_timeout=_SHUTDOWN_TIMEOUT,
            ):
                try:
                    _logger.info("fastapi APP started!")
                    startup_complete_event.set()
                    await shutdown_event.wait()
                except asyncio.CancelledError:
                    _logger.warning("Lifespan task cancelled")

        fastapi_app.state.shutdown_event = shutdown_event
        set_event_loop(fastapi_app, loop)

        set_fastapi_app(sender.app, fastapi_app)
        loop.run_until_complete(setup_task_manager())
        loop.run_until_complete(
            fastapi_lifespan(startup_complete_event, shutdown_event)
        )

    thread = threading.Thread(
        group=None,
        target=_init,
        name="fastapi_app",
        args=(startup_complete_event,),
        daemon=True,
    )
    thread.start()
    # ensure the fastapi app is ready before going on
    startup_complete_event.wait(_STARTUP_TIMEOUT * 1.1)


def on_worker_shutdown(sender, **_kwargs) -> None:
    with log_context(_logger, logging.INFO, "Worker Shuts-down"):
        assert isinstance(sender.app, Celery)
        fastapi_app = get_fastapi_app(sender.app)
        assert isinstance(fastapi_app, FastAPI)
        fastapi_app.state.shutdown_event.set()
