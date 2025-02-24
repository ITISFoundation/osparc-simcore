"""Main application to be deployed in for example uvicorn."""

import logging

from servicelib.logging_utils import config_all_loggers

from .core.application import create_app
from .core.settings import ApplicationSettings
from .modules.celery.client import CeleryTaskQueueClient
from .modules.celery.common import create_app

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
celery_app = create_app(_settings)

celery_app.conf["client"] = CeleryTaskQueueClient(celery_app)
fastapi_app.state.celery_app = celery_app

app = fastapi_app
