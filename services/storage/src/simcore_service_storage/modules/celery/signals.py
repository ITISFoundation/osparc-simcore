import asyncio
import logging
import threading
from typing import Final

from asgi_lifespan import LifespanManager
from celery import Celery  # type: ignore[import-untyped]
from fastapi import FastAPI
from servicelib.async_utils import cancel_wait_task

from ...core.application import create_app
from ...core.settings import ApplicationSettings
from ...modules.celery import get_event_loop, set_event_loop
from ...modules.celery.utils import (
    get_fastapi_app,
    set_celery_worker,
    set_fastapi_app,
)
from ...modules.celery.worker import CeleryTaskQueueWorker

_logger = logging.getLogger(__name__)

_LIFESPAN_TIMEOUT: Final[int] = 10


def on_worker_init(sender, **_kwargs) -> None:
    def _init_fastapi() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        shutdown_event = asyncio.Event()

        fastapi_app = create_app(ApplicationSettings.create_from_envs())

        async def lifespan():
            async with LifespanManager(
                fastapi_app,
                startup_timeout=_LIFESPAN_TIMEOUT,
                shutdown_timeout=_LIFESPAN_TIMEOUT,
            ):
                try:
                    await shutdown_event.wait()
                except asyncio.CancelledError:
                    _logger.warning("Lifespan task cancelled")

        lifespan_task = loop.create_task(lifespan())
        fastapi_app.state.lifespan_task = lifespan_task
        fastapi_app.state.shutdown_event = shutdown_event
        set_event_loop(fastapi_app, loop)

        set_fastapi_app(sender.app, fastapi_app)
        set_celery_worker(sender.app, CeleryTaskQueueWorker(sender.app))

        loop.run_forever()

    thread = threading.Thread(target=_init_fastapi, daemon=True)
    thread.start()


def on_worker_shutdown(sender, **_kwargs):
    assert isinstance(sender.app, Celery)

    fastapi_app = get_fastapi_app(sender.app)
    assert isinstance(fastapi_app, FastAPI)
    event_loop = get_event_loop(fastapi_app)

    async def shutdown():
        fastapi_app.state.shutdown_event.set()

        await cancel_wait_task(fastapi_app.state.lifespan_task, max_delay=5)

    asyncio.run_coroutine_threadsafe(shutdown(), event_loop)
