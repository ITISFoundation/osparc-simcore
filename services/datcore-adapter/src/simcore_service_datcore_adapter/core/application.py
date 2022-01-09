import logging
from typing import Optional

from fastapi import FastAPI
from models_library.basic_types import BootModeEnum
from servicelib.fastapi.tracing import setup_tracing

from ..api.module_setup import setup_api
from ..meta import api_version, api_vtag
from ..modules import pennsieve
from .events import (
    create_start_app_handler,
    create_stop_app_handler,
    on_shutdown,
    on_startup,
)
from .settings import Settings

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    if settings is None:
        settings = Settings.create_from_envs()

    logging.basicConfig(level=settings.LOG_LEVEL.value)
    logging.root.setLevel(settings.LOG_LEVEL.value)

    app = FastAPI(
        debug=bool(
            settings.SC_BOOT_MODE
            in [BootModeEnum.DEBUG, BootModeEnum.DEVELOPMENT, BootModeEnum.LOCAL]
        ),
        title="Datcore Adapter Service",
        description="Interfaces with Pennsieve storage service",
        version=api_version,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )

    logger.debug(settings)
    app.state.settings = settings

    # events
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))
    app.add_event_handler("shutdown", on_shutdown)

    # Routing
    setup_api(app)

    if settings.PENNSIEVE.PENNSIEVE_ENABLED:
        pennsieve.setup(app, settings.PENNSIEVE)

    if settings.DATCORE_ADAPTER_TRACING:
        setup_tracing(app, settings.DATCORE_ADAPTER_TRACING)

    return app
