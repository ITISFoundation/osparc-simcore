from fastapi import APIRouter, FastAPI

from .._meta import API_VTAG
from . import _health, _meta


def setup_api_routes(app: FastAPI):
    """
    Composes resources/sub-resources routers
    """
    app.include_router(_health.router)

    api_router = APIRouter(prefix=f"/{API_VTAG}")
    api_router.include_router(_meta.router, tags=["meta"])
    app.include_router(api_router)
