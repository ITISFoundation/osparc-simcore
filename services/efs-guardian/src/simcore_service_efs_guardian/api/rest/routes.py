from fastapi import APIRouter, FastAPI

from ..._meta import API_VTAG
from . import health


def setup_api_routes(app: FastAPI) -> None:
    """
    Composes resources/sub-resources routers
    """
    # healthcheck at / and at /vX/
    app.include_router(health.router)

    v0_router = APIRouter(prefix=f"/{API_VTAG}")
    v0_router.include_router(health.router)
    app.include_router(v0_router)
