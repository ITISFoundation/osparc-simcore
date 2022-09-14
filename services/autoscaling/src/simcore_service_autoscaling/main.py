"""Main application to be deployed by uvicorn (or equivalent) server

"""
import logging

from fastapi import FastAPI
from simcore_service_autoscaling.core.application import create_app
from simcore_service_autoscaling.core.settings import ApplicationSettings

the_settings = ApplicationSettings.create_from_envs()
logging.basicConfig(level=the_settings.log_level)
logging.root.setLevel(the_settings.log_level)

# SINGLETON FastAPI app
the_app: FastAPI = create_app(the_settings)
