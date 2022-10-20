from fastapi import APIRouter, FastAPI
from .._meta import API_VTAG
from . import _operations


def setup_api_routes(app: FastAPI):
    """
    Composes resources/sub-resources routers
    """
    router = APIRouter()
    router.include_router(_operations.router, tags=["operations"])
    #
    app.include_router(router, prefix=f"/{API_VTAG}")
