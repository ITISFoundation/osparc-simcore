from typing import Final

from fastapi import APIRouter

from ..core.settings import ApplicationSettings
from .routes import credits as _credits
from .routes import (
    files,
    function_job_collections_routes,
    function_jobs_routes,
    functions_routes,
    health,
    licensed_items,
    meta,
    programs,
    solvers,
    solvers_jobs,
    solvers_jobs_read,
    studies,
    studies_jobs,
    tasks,
    users,
    wallets,
)

_SOLVERS_PREFIX: Final[str] = "/solvers"
_FUNCTIONS_PREFIX: Final[str] = "/functions"
_FUNCTION_JOBS_PREFIX: Final[str] = "/function_jobs"
_FUNCTION_JOB_COLLECTIONS_PREFIX: Final[str] = "/function_job_collections"


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
    router.include_router(programs.router, tags=["programs"], prefix="/programs")
    router.include_router(solvers.router, tags=["solvers"], prefix=_SOLVERS_PREFIX)
    router.include_router(solvers_jobs.router, tags=["solvers"], prefix=_SOLVERS_PREFIX)
    router.include_router(
        solvers_jobs_read.router, tags=["solvers"], prefix=_SOLVERS_PREFIX
    )
    router.include_router(studies.router, tags=["studies"], prefix="/studies")
    router.include_router(studies_jobs.router, tags=["studies"], prefix="/studies")
    router.include_router(
        function_jobs_routes.function_job_router,
        tags=["function_jobs"],
        prefix=_FUNCTION_JOBS_PREFIX,
    )
    router.include_router(
        function_job_collections_routes.function_job_collections_router,
        tags=["function_job_collections"],
        prefix=_FUNCTION_JOB_COLLECTIONS_PREFIX,
    )
    router.include_router(wallets.router, tags=["wallets"], prefix="/wallets")
    router.include_router(_credits.router, tags=["credits"], prefix="/credits")
    router.include_router(
        licensed_items.router, tags=["licensed-items"], prefix="/licensed-items"
    )
    router.include_router(
        functions_routes.function_router, tags=["functions"], prefix=_FUNCTIONS_PREFIX
    )
    router.include_router(tasks.router, tags=["tasks"], prefix="/tasks")

    # NOTE: multiple-files upload is currently disabled
    # Web form to upload files at http://localhost:8000/v0/upload-form-view
    # Overcomes limitation of Swagger UI view
    # NOTE: As of 2020-10-07, Swagger UI doesn't support multiple file uploads in the same form field
    # as router.get("/upload-multiple-view")(files.files_upload_multiple_view)

    return router
