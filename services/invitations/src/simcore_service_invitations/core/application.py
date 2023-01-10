import logging

from api.routes import router
from fastapi import FastAPI

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME, SUMMARY
from .settings import WebApplicationSettings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:

    app = FastAPI(
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled, see below
    )
    # states
    app.state.settings = WebApplicationSettings()

    # routes
    app.router.include_router(router)

    return app
