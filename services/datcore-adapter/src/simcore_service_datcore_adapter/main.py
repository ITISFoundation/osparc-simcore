"""Main application to be deployed in for example uvicorn"""

import logging
from typing import Final

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from servicelib import tracing
from servicelib.fastapi.logging_lifespan import create_logging_shutdown_event
from simcore_service_datcore_adapter.core.application import create_app
from simcore_service_datcore_adapter.core.settings import ApplicationSettings

from ._meta import APP_NAME

_logger = logging.getLogger(__name__)

_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "aiocache",
    "botocore",
    "hpack",
)


def app_factory() -> FastAPI:
    app_settings = ApplicationSettings.create_from_envs()
    tracing_config = tracing.TracingConfig.create(
        service_name=APP_NAME, tracing_settings=app_settings.DATCORE_ADAPTER_TRACING
    )
    logging_shutdown_event = create_logging_shutdown_event(
        log_format_local_dev_enabled=app_settings.DATCORE_ADAPTER_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=app_settings.DATCORE_ADAPTER_LOG_FILTER_MAPPING,
        tracing_config=tracing_config,
        log_base_level=app_settings.log_level,
        noisy_loggers=_NOISY_LOGGERS,
    )

    _logger.info(
        "Application settings: %s",
        json_dumps(app_settings, indent=2, sort_keys=True),
    )
    app = create_app(settings=app_settings, tracing_config=tracing_config)
    app.add_event_handler("shutdown", logging_shutdown_event)
    return app
