import logging
from typing import Optional

from fastapi import FastAPI
from models_library.basic_types import BootModeEnum

from ..api.module_setup import setup_api
from ..meta import api_version, api_vtag
from ..modules import pennsieve
from .settings import Settings

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    if settings is None:
        settings = Settings.create_from_envs()

    logging.basicConfig(level=settings.DATCORE_ADAPTER_LOG_LEVEL.value)
    logging.root.setLevel(settings.DATCORE_ADAPTER_LOG_LEVEL.value)

    app = FastAPI(
        debug=bool(
            settings.SC_BOOT_MODE
            in [BootModeEnum.DEBUG, BootModeEnum.DEVELOPMENT, BootModeEnum.LOCAL]
        ),
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

    if settings.DATCORE_ADAPTER_PENNSIEVE.ENABLED:
        pennsieve.setup(app, settings.DATCORE_ADAPTER_PENNSIEVE)

    return app
