"""
    api app module
"""
from fastapi import APIRouter, FastAPI

from ..meta import api_vtag


def setup_api(app: FastAPI):
    router = APIRouter()

    app.include_router(router, prefix=f"/{api_vtag}")
