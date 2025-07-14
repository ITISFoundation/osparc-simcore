"""Main application to be deployed in for example uvicorn."""

import logging

from fastapi import FastAPI
from simcore_service_director_v2.core.application import create_app

_logger = logging.getLogger(__name__)


def app_factory() -> FastAPI:
    return create_app()
