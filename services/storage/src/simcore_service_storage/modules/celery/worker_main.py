"""Main application to be deployed in for example uvicorn."""

import logging

from celery.signals import worker_init, worker_shutdown  # type: ignore[import-untyped]
from servicelib.logging_utils import config_all_loggers
from simcore_celery_library.signals import (
    on_worker_init,
    on_worker_shutdown,
)
from simcore_service_storage.api._worker_tasks.tasks import setup_worker_tasks

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


assert _settings.STORAGE_CELERY
app = create_celery_app(_settings.STORAGE_CELERY)
worker_init.connect(on_worker_init)
worker_shutdown.connect(on_worker_shutdown)


setup_worker_tasks(app)
