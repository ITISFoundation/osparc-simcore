from functools import cache

from fastapi import APIRouter, FastAPI

from .._meta import API_VTAG
from . import health


@cache
def setup_api_routes(app: FastAPI):
    """
    Composes resources/sub-resources routers
    """

    # include operations in /
    app.include_router(health.router, tags=["operations"])

    router = APIRouter(prefix=f"/{API_VTAG}")
    # include the rest under /vX
    app.include_router(router)
