from fastapi import FastAPI, HTTPException
from servicelib.fastapi.exceptions_utils import (
    handle_errors_as_500,
    http_exception_as_json_response,
)

from ...exceptions.handlers import set_exception_handlers
from . import _health


def initialize_rest_api(app: FastAPI) -> None:
    set_exception_handlers(app)

    app.add_exception_handler(Exception, handle_errors_as_500)
    app.add_exception_handler(HTTPException, http_exception_as_json_response)

    app.include_router(_health.router)
