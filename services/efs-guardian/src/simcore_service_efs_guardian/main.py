"""Main application to be deployed by uvicorn (or equivalent) server

"""
import logging

from fastapi import FastAPI
from servicelib.logging_utils import config_all_loggers
from simcore_service_efs_guardian.core.application import create_app
from simcore_service_efs_guardian.core.settings import ApplicationSettings

the_settings = ApplicationSettings.create_from_envs()
logging.basicConfig(level=the_settings.log_level)
logging.root.setLevel(the_settings.log_level)
config_all_loggers(the_settings.EFS_GUARDIAN_LOG_FORMAT_LOCAL_DEV_ENABLED)

# SINGLETON FastAPI app
the_app: FastAPI = create_app(the_settings)
