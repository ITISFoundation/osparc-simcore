from fastapi import FastAPI
from . import endpoints_auth
from . import endpoints_user
from . import endpoints_check
from __version__ import api_version_prefix, api_version
from .config import is_testing_enabled


def create() -> FastAPI:

    # APPLICATION
    app = FastAPI(
        debug=is_testing_enabled,
        title="Public API Gateway",
        description="Platform's API Gateway for external clients",
        version=api_version,
        openapi_url=f"/api/{api_version_prefix}/openapi.json",
    )

    # ROUTES ----
    app.include_router(endpoints_check.router, tags=["check"])

    app.include_router(
        endpoints_auth.router, tags=["auth"], prefix=f"/{api_version_prefix}"
    )
    app.include_router(
        endpoints_user.router, tags=["users"], prefix=f"/{api_version_prefix}"
    )

    # TODO: add start/stop events here

    return app
