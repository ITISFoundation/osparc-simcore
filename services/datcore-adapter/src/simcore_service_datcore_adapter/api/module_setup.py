"""
    api app module
"""
from fastapi import APIRouter, FastAPI

from ..meta import api_vtag
from .routes import datasets, files, health, user


def setup_api(app: FastAPI):
    router = APIRouter()

    app.include_router(router, prefix=f"/{api_vtag}")
    app.include_router(health.router, tags=["healthcheck"], prefix=f"/{api_vtag}")
    app.include_router(user.router, tags=["user"], prefix=f"/{api_vtag}")
    app.include_router(datasets.router, tags=["datasets"], prefix=f"/{api_vtag}")
    app.include_router(files.router, tags=["files"], prefix=f"/{api_vtag}")
