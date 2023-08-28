"""Main application to be deployed by uvicorn (or equivalent) server

"""
import logging

from fastapi import FastAPI
from servicelib.logging_utils import config_all_loggers
from simcore_service_payments.core.application import create_app
from simcore_service_payments.core.settings import ApplicationSettings

_the_settings = ApplicationSettings.create_from_envs()

# SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
logging.basicConfig(level=_the_settings.log_level)  # NOSONAR
logging.root.setLevel(_the_settings.log_level)
config_all_loggers(_the_settings.INVITATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED)

# SINGLETON FastAPI app
the_app: FastAPI = create_app(_the_settings)
