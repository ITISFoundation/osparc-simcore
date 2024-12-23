from fastapi import APIRouter

from .._meta import API_VTAG
from .routes import (
    computations,
    computations_tasks,
    docker_networks,
    dynamic_scheduler,
    dynamic_services,
    health,
    meta,
)

# Info
meta_router = APIRouter()
meta_router.include_router(health.router)
meta_router.include_router(meta.router, prefix="/meta")

# Latest API
v2_router = APIRouter()
v2_router.include_router(
    computations.router, tags=["computations"], prefix="/computations"
)
v2_router.include_router(
    computations_tasks.router, tags=["computations"], prefix="/computations"
)
v2_router.include_router(
    dynamic_services.router, tags=["dynamic services"], prefix="/dynamic_services"
)
v2_router.include_router(
    docker_networks.router, tags=["docker networks"], prefix="/docker/networks"
)

v2_router.include_router(
    dynamic_scheduler.router, tags=["dynamic scheduler"], prefix="/dynamic_scheduler"
)


# root
api_router = APIRouter()
api_router.include_router(meta_router)
api_router.include_router(v2_router, prefix=f"/{API_VTAG}")

__all__ = ["api_router"]
