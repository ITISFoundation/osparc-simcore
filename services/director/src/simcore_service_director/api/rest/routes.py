from typing import Final

from fastapi import APIRouter, FastAPI, HTTPException
from servicelib.fastapi.exceptions_utils import (
    handle_errors_as_500,
    http_exception_as_json_response,
)

from . import _health, _running_interactive_services, _service_extras, _services

_V0_VTAG: Final[str] = "v0"


def setup_api_routes(app: FastAPI):
    """
    Composes resources/sub-resources routers
    """

    app.include_router(_health.router, tags=["operations"])
    app.include_router(_health.router, tags=["operations"], prefix=f"/{_V0_VTAG}")

    # include the rest under /vX
    api_router = APIRouter(prefix=f"/{_V0_VTAG}")
    api_router.include_router(_services.router, tags=["services"])
    api_router.include_router(_service_extras.router, tags=["services"])
    api_router.include_router(_running_interactive_services.router, tags=["services"])
    app.include_router(api_router)

    app.add_exception_handler(Exception, handle_errors_as_500)
    app.add_exception_handler(HTTPException, http_exception_as_json_response)
