"""Main application to be deployed in for example uvicorn.
"""
import logging

from fastapi import FastAPI
from servicelib.logging_utils import config_all_loggers
from simcore_service_catalog.core.application import create_app
from simcore_service_catalog.core.settings import ApplicationSettings

_the_settings = ApplicationSettings.create_from_envs()

# SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
logging.basicConfig(level=_the_settings.CATALOG_LOG_LEVEL.value)  # NOSONAR
logging.root.setLevel(_the_settings.CATALOG_LOG_LEVEL.value)
config_all_loggers(_the_settings.CATALOG_LOG_FORMAT_LOCAL_DEV_ENABLED)


# SINGLETON FastAPI app
the_app: FastAPI = create_app()
