""" Module to collect, tag and prefix all routes under 'main_router'

Setup and register all routes here form different modules
"""

from fastapi import APIRouter

from .._meta import API_VTAG
from . import (
    containers,
    containers_extension,
    containers_long_running_tasks,
    health,
    volumes,
)

main_router = APIRouter()
main_router.include_router(health.router)
main_router.include_router(
    containers.router,
    tags=["containers"],
    prefix=f"/{API_VTAG}",
)
main_router.include_router(
    containers_extension.router,
    tags=["containers"],
    prefix=f"/{API_VTAG}",
)
main_router.include_router(
    containers_long_running_tasks.router,
    tags=["containers"],
    prefix=f"/{API_VTAG}",
)
main_router.include_router(
    volumes.router,
    tags=["volumes"],
    prefix=f"/{API_VTAG}",
)

__all__: tuple[str, ...] = ("main_router",)
