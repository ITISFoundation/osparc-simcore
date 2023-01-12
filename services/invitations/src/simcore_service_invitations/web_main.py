"""Main application to be deployed by uvicorn (or equivalent) server

"""
import logging

from fastapi import FastAPI
from simcore_service_invitations.core.application import create_app
from simcore_service_invitations.core.settings import ApplicationSettings

the_settings = ApplicationSettings.create_from_envs()

# SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
logging.basicConfig(level=the_settings.log_level)  # NOSONAR
logging.root.setLevel(the_settings.log_level)

# SINGLETON FastAPI app
the_app: FastAPI = create_app()
