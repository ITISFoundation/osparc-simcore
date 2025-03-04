"""Main application to be deployed in for example uvicorn."""

import asyncio
import logging
import threading
from typing import Final

from asgi_lifespan import LifespanManager
from celery import Celery
from celery.signals import worker_init, worker_shutdown
from fastapi import FastAPI
from servicelib.background_task import cancel_wait_task
from servicelib.logging_utils import config_all_loggers
from simcore_service_storage.modules.celery import get_event_loop, set_event_loop
from simcore_service_storage.modules.celery.utils import (
    CeleryTaskQueueWorker,
    get_fastapi_app,
    set_celery_worker,
    set_fastapi_app,
)

from ...core.application import create_app
from ...core.settings import ApplicationSettings
from ._common import create_app as create_celery_app

_settings = ApplicationSettings.create_from_envs()

logging.basicConfig(level=_settings.log_level)  # NOSONAR
logging.root.setLevel(_settings.log_level)
config_all_loggers(
    log_format_local_dev_enabled=_settings.STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=_settings.STORAGE_LOG_FILTER_MAPPING,
    tracing_settings=_settings.STORAGE_TRACING,
)

_logger = logging.getLogger(__name__)

_LIFESPAN_TIMEOUT: Final[int] = 10


@worker_init.connect
def on_worker_init(sender, **_kwargs):
    def _init_fastapi():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        shutdown_event = asyncio.Event()

        fastapi_app = create_app(_settings)

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


@worker_shutdown.connect
def on_worker_shutdown(sender, **_kwargs):
    assert isinstance(sender.app, Celery)

    fastapi_app = get_fastapi_app(sender.app)
    assert isinstance(fastapi_app, FastAPI)
    event_loop = get_event_loop(fastapi_app)

    async def shutdown():
        fastapi_app.state.shutdown_event.set()

        await cancel_wait_task(fastapi_app.state.lifespan_task, max_delay=5)

    asyncio.run_coroutine_threadsafe(shutdown(), event_loop)


assert _settings.STORAGE_CELERY
app = create_celery_app(_settings.STORAGE_CELERY)
