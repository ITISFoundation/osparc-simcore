"""Main application to be deployed by uvicorn (or equivalent) server"""

from fastapi import FastAPI
from servicelib.logging_utils import setup_loggers
from simcore_service_resource_usage_tracker.core.application import create_app
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings

the_settings = ApplicationSettings.create_from_envs()

setup_loggers(
    log_format_local_dev_enabled=the_settings.RESOURCE_USAGE_TRACKER_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=the_settings.RESOURCE_USAGE_TRACKER_LOG_FILTER_MAPPING,
    tracing_settings=the_settings.RESOURCE_USAGE_TRACKER_TRACING,
    log_base_level=the_settings.log_level,
    noisy_loggers=None,
)

# SINGLETON FastAPI app
the_app: FastAPI = create_app(the_settings)
