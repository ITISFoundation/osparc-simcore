"""Main application to be deployed in for example uvicorn."""

import logging

from celery.contrib.abortable import AbortableTask
from celery.signals import worker_init, worker_shutdown
from servicelib.logging_utils import config_all_loggers
from simcore_service_storage.modules.celery.signals import (
    on_worker_init,
    on_worker_shutdown,
)

from ...core.settings import ApplicationSettings
from ._common import create_app as create_celery_app
from .tasks import export_data

_settings = ApplicationSettings.create_from_envs()

logging.basicConfig(level=_settings.log_level)  # NOSONAR
logging.root.setLevel(_settings.log_level)
config_all_loggers(
    log_format_local_dev_enabled=_settings.STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=_settings.STORAGE_LOG_FILTER_MAPPING,
    tracing_settings=_settings.STORAGE_TRACING,
)

_logger = logging.getLogger(__name__)

assert _settings.STORAGE_CELERY
app = create_celery_app(_settings.STORAGE_CELERY)
worker_init.connect(on_worker_init)
worker_shutdown.connect(on_worker_shutdown)
app.task(name="export_data", bind=True, base=AbortableTask)(export_data)
