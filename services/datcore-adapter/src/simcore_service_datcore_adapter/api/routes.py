"""
api app module
"""

from fastapi import APIRouter, FastAPI

from .._meta import API_VTAG
from .rest import datasets, files, health, user


def setup_rest_api_routes(app: FastAPI) -> None:
    router = APIRouter()

    app.include_router(router, prefix=f"/{API_VTAG}")
    app.include_router(health.router, tags=["healthcheck"], prefix=f"/{API_VTAG}")
    app.include_router(user.router, tags=["user"], prefix=f"/{API_VTAG}")
    app.include_router(datasets.router, tags=["datasets"], prefix=f"/{API_VTAG}")
    app.include_router(files.router, tags=["files"], prefix=f"/{API_VTAG}")
