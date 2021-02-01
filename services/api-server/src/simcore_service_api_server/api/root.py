from fastapi import APIRouter

from ..core.settings import AppSettings
from .routes import files, health, jobs, meta, solvers, users


def create_router(settings: AppSettings):
    router = APIRouter()
    router.include_router(health.router)

    # API
    router.include_router(meta.router, tags=["meta"], prefix="/meta")
    router.include_router(users.router, tags=["users"], prefix="/me")
    router.include_router(files.router, tags=["files"], prefix="/files")

    if settings.fake_server_enabled:
        router.include_router(solvers.router, tags=["solvers"], prefix="/solvers")
        router.include_router(jobs.router, tags=["jobs"], prefix="/jobs")

    # NOTE: multiple-files upload is currently disabled
    # Web form to upload files at http://localhost:8000/v0/upload-form-view
    # Overcomes limitation of Swagger UI view
    # NOTE: As of 2020-10-07, Swagger UI doesn't support multiple file uploads in the same form field
    # router.get("/upload-multiple-view")(files.files_upload_multiple_view)

    return router
