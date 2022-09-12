from fastapi import APIRouter, FastAPI

from .._meta import API_VTAG
from . import _operations


def setup_api_routes(app: FastAPI):
    """
    Composes resources/sub-resources routers
    """
    router = APIRouter()

    # include operations in /
    app.include_router(_operations.router, tags=["operations"])

    # include the rest under /vX
    app.include_router(router, prefix=f"/{API_VTAG}")
