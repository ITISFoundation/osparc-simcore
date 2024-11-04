from fastapi import APIRouter, FastAPI, HTTPException
from servicelib.fastapi.exceptions_utils import (
    handle_errors_as_500,
    http_exception_as_json_response,
)

from .._meta import API_VTAG
from . import _health, _running_interactive_services, _service_extras, _services


def setup_api_routes(app: FastAPI):
    """
    Composes resources/sub-resources routers
    """

    app.include_router(_health.router, tags=["operations"])

    # include the rest under /vX
    api_router = APIRouter(prefix=f"/{API_VTAG}")
    api_router.include_router(_services.router, tags=["services"])
    api_router.include_router(_service_extras.router, tags=["services"])
    api_router.include_router(_running_interactive_services.router, tags=["services"])
    app.include_router(api_router)

    app.add_exception_handler(Exception, handle_errors_as_500)
    app.add_exception_handler(HTTPException, http_exception_as_json_response)
