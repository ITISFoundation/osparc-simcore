from fastapi import APIRouter

from ..core.settings import AppSettings
from .routes import health, meta


def create_router(_: AppSettings):
    router = APIRouter()
    router.include_router(health.router)

    # API
    router.include_router(meta.router, tags=["meta"], prefix="/meta")

    return router
