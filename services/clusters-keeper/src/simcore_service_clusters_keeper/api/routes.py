from fastapi import APIRouter, FastAPI
from servicelib.fastapi.application_setup import ensure_single_setup

from .._meta import API_VTAG
from . import health


@ensure_single_setup
def setup_api_routes(app: FastAPI):
    """
    Composes resources/sub-resources routers
    """

    # include operations in /
    app.include_router(health.router, tags=["operations"])

    router = APIRouter(prefix=f"/{API_VTAG}")
    # include the rest under /vX
    app.include_router(router)
