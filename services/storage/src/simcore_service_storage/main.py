"""Main application to be deployed in for example uvicorn."""

import asyncio
import logging

from servicelib.logging_utils import config_all_loggers
from simcore_service_storage.modules.celery import setup_celery

from .core.application import create_app
from .core.settings import ApplicationSettings

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
setup_celery(fastapi_app)

app = fastapi_app
