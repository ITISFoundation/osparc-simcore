"""Main application to be deployed by uvicorn (or equivalent) server"""

import logging
from typing import Final

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from servicelib.fastapi.logging_lifespan import setup_logging_shutdown_event
from simcore_service_director.core.application import create_app
from simcore_service_director.core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)

_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "httpcore",
    "httpx",
    "werkzeug",
)


def app_factory() -> FastAPI:
    app_settings = ApplicationSettings.create_from_envs()
    logging_shutdown_event = setup_logging_shutdown_event(
        log_format_local_dev_enabled=app_settings.DIRECTOR_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=app_settings.DIRECTOR_LOG_FILTER_MAPPING,
        tracing_settings=app_settings.DIRECTOR_TRACING,
        log_base_level=app_settings.log_level,
        noisy_loggers=_NOISY_LOGGERS,
    )

    _logger.info(
        "Application settings: %s",
        json_dumps(app_settings, indent=2, sort_keys=True),
    )
    app = create_app(settings=app_settings)
    app.add_event_handler("shutdown", logging_shutdown_event)
    return app
