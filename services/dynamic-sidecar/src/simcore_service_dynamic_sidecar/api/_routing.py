# module acting as root for all routes

from fastapi import APIRouter

from .._meta import API_VTAG
from .containers import containers_router
from .health import health_router

# setup and register all routes here form different modules
main_router = APIRouter()
main_router.include_router(health_router)
main_router.include_router(containers_router, prefix=f"/{API_VTAG}")

__all__ = ["main_router"]
