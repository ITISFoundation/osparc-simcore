# module acting as root for all routes

from fastapi import APIRouter

from .compose import compose_router
from .container import container_router
from .containers import containers_router
from .health import health_router
from .mocked import mocked_router
from .._meta import api_vtag

# setup and register all routes here form different modules
main_router = APIRouter()
main_router.include_router(health_router)
main_router.include_router(compose_router, prefix=f"/{api_vtag}")
main_router.include_router(containers_router, prefix=f"/{api_vtag}")
main_router.include_router(container_router, prefix=f"/{api_vtag}")
main_router.include_router(mocked_router)

__all__ = ["main_router"]
