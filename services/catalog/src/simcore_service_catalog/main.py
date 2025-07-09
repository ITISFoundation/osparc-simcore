"""Main application to be deployed in for example uvicorn."""

from typing import Final

from fastapi import FastAPI
from servicelib.logging_utils import setup_loggers
from simcore_service_catalog.core.application import create_app
from simcore_service_catalog.core.settings import ApplicationSettings

_the_settings = ApplicationSettings.create_from_envs()

_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "aio_pika",
    "aiobotocore",
    "aiormq",
    "botocore",
    "httpcore",
    "werkzeug",
)

setup_loggers(
    log_format_local_dev_enabled=_the_settings.CATALOG_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=_the_settings.CATALOG_LOG_FILTER_MAPPING,
    tracing_settings=_the_settings.CATALOG_TRACING,
    log_base_level=_the_settings.log_level,
    noisy_loggers=_NOISY_LOGGERS,
)


# SINGLETON FastAPI app
the_app: FastAPI = create_app()
