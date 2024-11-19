"""Main application to be deployed by uvicorn (or equivalent) server

"""

import logging

from fastapi import FastAPI
from servicelib.logging_utils import config_all_loggers
from simcore_service_director.core.application import create_app
from simcore_service_director.core.settings import ApplicationSettings

_the_settings = ApplicationSettings.create_from_envs()

# SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
logging.basicConfig(level=_the_settings.DIRECTOR_LOGLEVEL)
logging.root.setLevel(_the_settings.DIRECTOR_LOGLEVEL)
config_all_loggers(
    log_format_local_dev_enabled=_the_settings.DIRECTOR_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=_the_settings.DIRECTOR_LOG_FILTER_MAPPING,
)

# SINGLETON FastAPI app
the_app: FastAPI = create_app(_the_settings)
