"""Main application to be deployed in for example uvicorn."""

import logging
import os

from celery.signals import worker_init, worker_shutdown  # type: ignore[import-untyped]
from celery_library.common import create_app as create_celery_app
from celery_library.signals import (
    on_worker_init,
    on_worker_shutdown,
)
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.logging_utils import setup_loggers
from servicelib.tracing import TracingConfig

from ...api._worker_tasks.tasks import setup_worker_tasks
from ...core.application import create_app
from ...core.settings import ApplicationSettings

_settings = ApplicationSettings.create_from_envs()
_tracing_config = TracingConfig.create(
    tracing_settings=_settings.STORAGE_TRACING,
    service_name="storage-celery-worker",
)

setup_loggers(
    log_format_local_dev_enabled=_settings.STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=_settings.STORAGE_LOG_FILTER_MAPPING,
    tracing_config=_tracing_config,
    log_base_level=_settings.log_level,
    noisy_loggers=None,
)


_logger = logging.getLogger(__name__)

assert _settings.STORAGE_CELERY  # nosec
app = create_celery_app(_settings.STORAGE_CELERY)
_logger.info("Starting worker with pool=%s", os.environ.get("CELERY_POOL"))

app_server = FastAPIAppServer(app=create_app(_settings, tracing_config=_tracing_config))


def worker_init_wrapper(sender, **kwargs):
    return on_worker_init(sender, app_server, **kwargs)


worker_init.connect(worker_init_wrapper)
worker_shutdown.connect(on_worker_shutdown)


setup_worker_tasks(app)
