import logging

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from models_library.basic_types import BootModeEnum
from servicelib.fastapi import timing_middleware
from servicelib.fastapi.monitoring import (
    initialize_prometheus_instrumentation,
)
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import initialize_tracing
from starlette.middleware.base import BaseHTTPMiddleware

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_NAME,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.rest import initialize_rest_api
from . import events
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)

_LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
_NOISY_LOGGERS = (
    "aio_pika",
    "aiobotocore",
    "aiormq",
    "botocore",
    "httpcore",
    "werkzeug",
)


def create_app() -> FastAPI:
    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + _LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)

    settings = ApplicationSettings.create_from_envs()
    _logger.debug(settings.model_dump_json(indent=2))

    app = FastAPI(
        debug=settings.SC_BOOT_MODE
        in [BootModeEnum.DEBUG, BootModeEnum.DEVELOPMENT, BootModeEnum.LOCAL],
        title=PROJECT_NAME,
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
        lifespan=events.create_app_lifespan(),
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings

    # MIDDLEWARES
    if settings.CATALOG_TRACING:
        initialize_tracing(app, settings.CATALOG_TRACING, APP_NAME)

    if settings.CATALOG_PROMETHEUS_INSTRUMENTATION_ENABLED:
        initialize_prometheus_instrumentation(app)

    if settings.SC_BOOT_MODE != BootModeEnum.PRODUCTION:
        # middleware to time requests (ONLY for development)
        app.add_middleware(
            BaseHTTPMiddleware, dispatch=timing_middleware.add_process_time_header
        )

    app.add_middleware(GZipMiddleware)

    # ROUTES & ERROR HANDLERS
    initialize_rest_api(app)

    return app
