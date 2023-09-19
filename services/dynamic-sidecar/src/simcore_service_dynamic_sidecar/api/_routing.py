""" Module to collect, tag and prefix all routes under 'main_router'

Setup and register all routes here form different modules
"""

from fastapi import APIRouter, FastAPI

from .._meta import API_VTAG
from ..core.settings import ApplicationSettings
from . import (
    containers,
    containers_extension,
    containers_long_running_tasks,
    health,
    prometheus_metrics,
    volumes,
)


def get_main_router(app: FastAPI) -> APIRouter:
    settings: ApplicationSettings = app.state.settings

    main_router = APIRouter()

    main_router.include_router(health.router)
    if settings.are_prometheus_metrics_enabled:
        main_router.include_router(prometheus_metrics.router)

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

    return main_router


__all__: tuple[str, ...] = ("get_main_router",)
