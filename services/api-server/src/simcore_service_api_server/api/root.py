from typing import Final

from fastapi import APIRouter
from simcore_service_api_server.api.routes import solvers_jobs_getters

from ..core.settings import ApplicationSettings
from .routes import (
    files,
    health,
    meta,
    solvers,
    solvers_jobs,
    studies,
    studies_jobs,
    users,
    wallets,
)

_SOLVERS_PREFIX: Final[str] = "/solvers"


def create_router(settings: ApplicationSettings):
    assert (  # nosec
        settings
    ), "Might be used e.g. to enable/disable entrypoints settings.API_SERVER_DEV_FEATURES_ENABLED"
    router = APIRouter()
    router.include_router(health.router)

    # API
    router.include_router(meta.router, tags=["meta"], prefix="/meta")
    router.include_router(users.router, tags=["users"], prefix="/me")
    router.include_router(files.router, tags=["files"], prefix="/files")
    router.include_router(solvers.router, tags=["solvers"], prefix=_SOLVERS_PREFIX)
    router.include_router(solvers_jobs.router, tags=["solvers"], prefix=_SOLVERS_PREFIX)
    router.include_router(
        solvers_jobs_getters.router, tags=["solvers"], prefix=_SOLVERS_PREFIX
    )
    router.include_router(studies.router, tags=["studies"], prefix="/studies")
    router.include_router(studies_jobs.router, tags=["studies"], prefix="/studies")
    router.include_router(wallets.router, tags=["wallets"], prefix="/wallets")

    # NOTE: multiple-files upload is currently disabled
    # Web form to upload files at http://localhost:8000/v0/upload-form-view
    # Overcomes limitation of Swagger UI view
    # NOTE: As of 2020-10-07, Swagger UI doesn't support multiple file uploads in the same form field
    # as router.get("/upload-multiple-view")(files.files_upload_multiple_view)

    return router
