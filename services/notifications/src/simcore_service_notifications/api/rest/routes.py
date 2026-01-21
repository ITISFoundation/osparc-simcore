from fastapi import APIRouter, FastAPI, HTTPException
from servicelib.fastapi.exceptions_utils import (
    handle_errors_as_500,
    http_exception_as_json_response,
)

from ..._meta import API_VTAG
from ...exceptions.handlers import set_exception_handlers
from . import _health, _notifications


def initialize_rest_api(app: FastAPI) -> None:
    app.include_router(_health.router)

    api_router = APIRouter(prefix=f"/{API_VTAG}")
    api_router.include_router(_notifications.router, tags=["notifications"])
    app.include_router(api_router)

    set_exception_handlers(app)

    app.add_exception_handler(Exception, handle_errors_as_500)
    app.add_exception_handler(HTTPException, http_exception_as_json_response)
