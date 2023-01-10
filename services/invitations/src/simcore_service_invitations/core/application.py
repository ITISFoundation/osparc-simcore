import logging

from fastapi import FastAPI

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME
from ..api.routes import setup_api_routes
from .settings import ApplicationSettings

logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings) -> FastAPI:

    logger.debug("app settings: %s", settings.json(indent=1))

    app = FastAPI(
        debug=settings.debug,
        title=PROJECT_NAME,
        description="Service that manages creation and validation of registration invitations",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )

    app.state.settings = settings

    setup_api_routes(app)

    return app
