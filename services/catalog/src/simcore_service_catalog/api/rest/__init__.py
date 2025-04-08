from fastapi import FastAPI
from servicelib.fastapi.http_error import set_app_default_http_error_handlers

from .routes import setup_rest_api_routes


def initialize_rest_api(app: FastAPI):

    setup_rest_api_routes(app)

    # defaults error handling
    set_app_default_http_error_handlers(app)
