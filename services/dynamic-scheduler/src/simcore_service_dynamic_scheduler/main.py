"""Main application to be deployed by uvicorn (or equivalent) server"""

from fastapi import FastAPI
from servicelib.logging_utils import setup_loggers
from simcore_service_dynamic_scheduler.core.application import create_app
from simcore_service_dynamic_scheduler.core.settings import ApplicationSettings

_the_settings = ApplicationSettings.create_from_envs()
setup_loggers(
    log_format_local_dev_enabled=_the_settings.DYNAMIC_SCHEDULER_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=_the_settings.DYNAMIC_SCHEDULER_LOG_FILTER_MAPPING,
    tracing_settings=_the_settings.DYNAMIC_SCHEDULER_TRACING,
    log_base_level=_the_settings.log_level,
    noisy_loggers=None,
)

# SINGLETON FastAPI app
the_app: FastAPI = create_app(_the_settings)
