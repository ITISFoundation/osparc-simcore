from fastapi import APIRouter, FastAPI

from .._meta import API_VTAG
from .routes import (
    computations,
    computations_tasks,
    dynamic_scheduler,
    dynamic_services,
    health,
    meta,
)


def setup_api_routes(app: FastAPI) -> None:
    """
    Composes resources/sub-resources routers
    """
    # Info
    info_router = APIRouter()
    info_router.include_router(health.router)
    info_router.include_router(meta.router)

    # Latest API
    v2_router = APIRouter(prefix=f"/{API_VTAG}")
    v2_router.include_router(computations.router)
    v2_router.include_router(computations_tasks.router)
    v2_router.include_router(dynamic_services.router)
    v2_router.include_router(dynamic_scheduler.router)

    # root
    api_router = APIRouter()
    api_router.include_router(info_router)
    api_router.include_router(v2_router)

    app.include_router(api_router)
