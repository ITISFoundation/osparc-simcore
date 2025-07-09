"""Main application to be deployed by uvicorn (or equivalent) server"""

from fastapi import FastAPI
from servicelib.logging_utils import setup_loggers
from simcore_service_efs_guardian.core.application import create_app
from simcore_service_efs_guardian.core.settings import ApplicationSettings

the_settings = ApplicationSettings.create_from_envs()
setup_loggers(
    log_format_local_dev_enabled=the_settings.EFS_GUARDIAN_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=the_settings.EFS_GUARDIAN_LOG_FILTER_MAPPING,
    tracing_settings=the_settings.EFS_GUARDIAN_TRACING,
    log_base_level=the_settings.log_level,
    noisy_loggers=None,
)

# SINGLETON FastAPI app
the_app: FastAPI = create_app(the_settings)
