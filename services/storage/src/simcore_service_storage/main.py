"""Main application to be deployed in for example uvicorn."""

import logging

from servicelib.logging_utils import config_all_loggers

from .core.application import create_app
from .core.settings import ApplicationSettings
from .modules.celery.client import CeleryClientInterface
from .modules.celery.client.utils import attach_to_fastapi
from .modules.celery.utils import create_celery_app

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
celery_app = create_celery_app(ApplicationSettings.create_from_envs())

celery_app.conf["client_interface"] = CeleryClientInterface(celery_app)
attach_to_fastapi(fastapi_app, celery_app)

app = fastapi_app
