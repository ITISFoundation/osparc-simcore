"""Main application to be deployed in for example uvicorn."""

import logging
from typing import Final

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from servicelib.fastapi.logging_lifespan import create_logging_lifespan
from simcore_service_catalog.core.application import create_app
from simcore_service_catalog.core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "aio_pika",
    "aiobotocore",
    "aiormq",
    "botocore",
    "httpcore",
    "werkzeug",
)


def app_factory() -> FastAPI:
    app_settings = ApplicationSettings.create_from_envs()
    logging_lifespan = create_logging_lifespan(
        log_format_local_dev_enabled=app_settings.CATALOG_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=app_settings.CATALOG_LOG_FILTER_MAPPING,
        tracing_settings=app_settings.CATALOG_TRACING,
        log_base_level=app_settings.log_level,
        noisy_loggers=_NOISY_LOGGERS,
    )

    _logger.info(
        "Application settings: %s",
        json_dumps(app_settings, indent=2, sort_keys=True),
    )

    return create_app(settings=app_settings, logging_lifespan=logging_lifespan)
