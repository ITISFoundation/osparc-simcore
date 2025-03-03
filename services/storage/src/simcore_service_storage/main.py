"""Main application to be deployed in for example uvicorn."""

import logging

from servicelib.logging_utils import config_all_loggers
from simcore_service_storage.modules.celery._utils import (
    set_celery_app,
    set_celery_client,
)

from .core.application import create_app
from .core.settings import ApplicationSettings
from .modules.celery._common import create_app as create_celery_app
from .modules.celery.client import CeleryTaskQueueClient

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

set_celery_app(fastapi_app, celery_app)
set_celery_client(fastapi_app, CeleryTaskQueueClient(celery_app))

app = fastapi_app
