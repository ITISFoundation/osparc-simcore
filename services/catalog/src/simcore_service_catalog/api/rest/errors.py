from fastapi import FastAPI
from servicelib.fastapi.http_error import set_app_default_http_error_handlers


def setup_rest_api_error_handlers(app: FastAPI):
    set_app_default_http_error_handlers(app)
