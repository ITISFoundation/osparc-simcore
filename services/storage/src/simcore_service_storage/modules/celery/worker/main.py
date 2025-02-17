"""Main application to be deployed in for example uvicorn."""

import asyncio
import logging
import threading

from asgi_lifespan import LifespanManager
from celery.signals import worker_init, worker_shutdown
from servicelib.logging_utils import config_all_loggers
from simcore_service_storage.core.application import create_app
from simcore_service_storage.core.settings import ApplicationSettings
from simcore_service_storage.modules.celery.application import create_celery_app
from simcore_service_storage.modules.celery.tasks import archive

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

fastapi_app = create_app(_settings)

celery_app = create_celery_app(_settings)
celery_app.task(name="archive")(archive)


@worker_init.connect
def on_worker_init(**_kwargs):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    shutdown_event = asyncio.Event()

    async def lifespan():
        async with LifespanManager(fastapi_app):
            _logger.error("FastAPI lifespan started")
            try:
                await shutdown_event.wait()
            except asyncio.CancelledError:
                _logger.error("Lifespan task cancelled")
            _logger.error("FastAPI lifespan ended")

    lifespan_task = loop.create_task(lifespan())
    fastapi_app.state.lifespan_task = lifespan_task
    fastapi_app.state.shutdown_event = shutdown_event
    fastapi_app.state.loop = loop  # Store the loop for shutdown

    def run_loop():
        loop.run_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()


@worker_shutdown.connect
def on_worker_shutdown(**_kwargs):
    loop = fastapi_app.state.loop

    async def shutdown():
        fastapi_app.state.shutdown_event.set()
        fastapi_app.state.lifespan_task.cancel()
        try:
            await fastapi_app.state.lifespan_task
        except asyncio.CancelledError:
            pass

    asyncio.run_coroutine_threadsafe(shutdown(), loop)

    _logger.error("FastAPI lifespan stopped.")


celery_app.conf.fastapi_app = fastapi_app
app = celery_app
