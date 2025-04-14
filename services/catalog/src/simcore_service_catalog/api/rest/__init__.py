from fastapi import FastAPI

from .errors import setup_rest_api_error_handlers
from .routes import setup_rest_api_routes


def initialize_rest_api(app: FastAPI):

    setup_rest_api_routes(app)
    setup_rest_api_error_handlers(app)
