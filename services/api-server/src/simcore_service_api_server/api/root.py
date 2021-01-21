from fastapi import APIRouter

from ..core.settings import AppSettings
from .routes import files, health, jobs, meta, solvers, users


def create_router(settings: AppSettings):
    router = APIRouter()
    router.include_router(health.router)

    # API
    router.include_router(meta.router, tags=["meta"], prefix="/meta")
    router.include_router(users.router, tags=["users"], prefix="/me")
    if settings.fake_server_enabled:
        router.include_router(files.router, tags=["files"], prefix="/files")
        router.include_router(solvers.router, tags=["solvers"], prefix="/solvers")
        router.include_router(jobs.router, tags=["jobs"], prefix="/jobs")

    return router
