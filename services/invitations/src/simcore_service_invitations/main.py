"""Main application to be deployed by uvicorn (or equivalent) server"""

import logging

from common_library.json_serialization import json_dumps
from fastapi import FastAPI

from simcore_service_invitations.core.application import create_app
from simcore_service_invitations.core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def app_factory() -> FastAPI:
    app_settings = ApplicationSettings.create_from_envs()

    _logger.info(
        "Application settings: %s",
        json_dumps(app_settings, indent=2, sort_keys=True),
    )
    return create_app(settings=app_settings)
