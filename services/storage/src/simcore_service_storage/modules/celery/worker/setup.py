"""Main application to be deployed in for example uvicorn."""

import asyncio
import logging
import threading

from asgi_lifespan import LifespanManager
from celery.signals import worker_init, worker_shutdown
from servicelib.background_task import cancel_wait_task
from servicelib.logging_utils import config_all_loggers

from ....core.application import create_app
from ....core.settings import ApplicationSettings
from ....modules.celery.tasks import sync_archive
from ....modules.celery.utils import create_celery_app
from ._interface import CeleryWorkerInterface

_settings = ApplicationSettings.create_from_envs()

# SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
logging.basicConfig(level=_settings.log_level)  # NOSONAR
logging.root.setLevel(_settings.log_level)
config_all_loggers(
    log_format_local_dev_enabled=_settings.STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=_settings.STORAGE_LOG_FILTER_MAPPING,
    tracing_settings=_settings.STORAGE_TRACING,
)

_logger = logging.getLogger(__name__)


@worker_init.connect
def on_worker_init(sender, **_kwargs):
    def shhsshhshs():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        shutdown_event = asyncio.Event()

        fastapi_app = create_app(_settings)

        async def lifespan():
            async with LifespanManager(
                fastapi_app, startup_timeout=30, shutdown_timeout=30
            ):
                try:
                    await shutdown_event.wait()
                except asyncio.CancelledError:
                    _logger.warning("Lifespan task cancelled")

        lifespan_task = loop.create_task(lifespan())
        fastapi_app.state.lifespan_task = lifespan_task
        fastapi_app.state.shutdown_event = shutdown_event

        celery_worker_interface = CeleryWorkerInterface(sender.app)

        sender.app.conf["fastapi_app"] = fastapi_app
        sender.app.conf["loop"] = loop
        sender.app.conf["worker_interface"] = celery_worker_interface

        loop.run_forever()

    thread = threading.Thread(target=shhsshhshs, daemon=True)
    thread.start()


@worker_shutdown.connect
def on_worker_shutdown(sender, **_kwargs):
    loop = sender.app.conf["loop"]
    fastapi_app = sender.app.conf["fastapi_app"]

    async def shutdown():
        fastapi_app.state.shutdown_event.set()

        await cancel_wait_task(fastapi_app.state.lifespan_task, max_delay=5)

    asyncio.run_coroutine_threadsafe(shutdown(), loop)


celery_app = create_celery_app(ApplicationSettings.create_from_envs())
celery_app.task(name=sync_archive.__name__, bind=True)(sync_archive)

app = celery_app
