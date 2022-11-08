import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import setup_tracing

from ..api.errors.http_error import http_error_handler
from ..api.errors.validation_error import http422_error_handler
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

LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
NOISY_LOGGERS = (
    "aiocache",
    "botocore",
    "hpack",
)

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    if settings is None:
        settings = Settings.create_from_envs()
    assert settings  # nosec

    logging.basicConfig(level=settings.LOG_LEVEL.value)
    logging.root.setLevel(settings.LOG_LEVEL.value)
    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)
    logger.debug("App settings:\n%s", settings.json(indent=2))

    app = FastAPI(
        debug=settings.debug,
        title="Datcore Adapter Service",
        description="Interfaces with Pennsieve storage service",
        version=api_version,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )
    override_fastapi_openapi_method(app)

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

    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)

    return app
