"""
api app module
"""

from fastapi import APIRouter, FastAPI
from servicelib.fastapi.application_setup import ensure_single_setup

from .._meta import API_VTAG
from .rest import datasets, files, health, user


@ensure_single_setup
def setup_rest_api_routes(app: FastAPI) -> None:
    router = APIRouter(prefix=f"/{API_VTAG}")

    router.include_router(health.router, tags=["healthcheck"])
    router.include_router(user.router, tags=["user"])
    router.include_router(datasets.router, tags=["datasets"])
    router.include_router(files.router, tags=["files"])

    app.include_router(router)
