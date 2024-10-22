"""Main application to be deployed by uvicorn (or equivalent) server

"""

import logging

from fastapi import FastAPI
from servicelib.logging_utils import config_all_loggers
from simcore_service_dynamic_scheduler.core.application import create_app
from simcore_service_dynamic_scheduler.core.settings import ApplicationSettings

_the_settings = ApplicationSettings.create_from_envs()

logging.basicConfig(level=_the_settings.DYNAMIC_SCHEDULER_LOGLEVEL)
logging.root.setLevel(_the_settings.DYNAMIC_SCHEDULER_LOGLEVEL)
config_all_loggers(
    log_format_local_dev_enabled=_the_settings.DYNAMIC_SCHEDULER_LOG_FORMAT_LOCAL_DEV_ENABLED
)

# SINGLETON FastAPI app
the_app: FastAPI = create_app(_the_settings)
