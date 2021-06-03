import logging
from typing import Optional

from fastapi import FastAPI

from ..api.module_setup import setup_api
from ..meta import api_version, api_vtag
from .settings import AppSettings

logger = logging.getLogger(__name__)


def create_app(settings: Optional[AppSettings] = None) -> FastAPI:
    if settings is None:
        settings = AppSettings()

    logging.basicConfig(level=settings.loglevel)
    logging.root.setLevel(settings.loglevel)

    app = FastAPI(
        debug=settings.debug,
        title="Components Catalog Service",
        description="Manages and maintains a **catalog** of all published components (e.g. macro-algorithms, scripts, etc)",
        version=api_version,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )

    logger.debug(settings)
    app.state.settings = settings

    setup_api(app)

    return app
