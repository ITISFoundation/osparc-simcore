import logging

from common_library.basic_types import BootModeEnum
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_pagination import add_pagination
from servicelib.fastapi import timing_middleware
from servicelib.fastapi.http_error import set_app_default_http_error_handlers
from servicelib.fastapi.monitoring import (
    setup_prometheus_instrumentation,
)
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import (
    initialize_fastapi_app_tracing,
    setup_tracing,
)
from starlette.middleware.base import BaseHTTPMiddleware

from .._meta import API_VERSION, API_VTAG, APP_NAME
from ..api.routes import setup_rest_api_routes
from ..modules import pennsieve
from .events import (
    create_start_app_handler,
    create_stop_app_handler,
    on_shutdown,
    on_startup,
)
from .settings import ApplicationSettings

LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
NOISY_LOGGERS = (
    "aiocache",
    "botocore",
    "hpack",
)

_logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings) -> FastAPI:
    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)

    _logger.debug("App settings:\n%s", settings.model_dump_json(indent=1))

    app = FastAPI(
        debug=settings.SC_BOOT_MODE
        in [BootModeEnum.DEBUG, BootModeEnum.DEVELOPMENT, BootModeEnum.LOCAL],
        title=APP_NAME,
        description="Interfaces with Pennsieve storage service",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )
    override_fastapi_openapi_method(app)
    add_pagination(app)

    app.state.settings = settings

    if app.state.settings.DATCORE_ADAPTER_TRACING:
        setup_tracing(
            app,
            app.state.settings.DATCORE_ADAPTER_TRACING,
            APP_NAME,
        )
    if app.state.settings.DATCORE_ADAPTER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    if settings.SC_BOOT_MODE != BootModeEnum.PRODUCTION:
        # middleware to time requests (ONLY for development)
        app.add_middleware(
            BaseHTTPMiddleware, dispatch=timing_middleware.add_process_time_header
        )
    app.add_middleware(GZipMiddleware)

    if app.state.settings.DATCORE_ADAPTER_TRACING:
        initialize_fastapi_app_tracing(app)

    # events
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))
    app.add_event_handler("shutdown", on_shutdown)

    # Routing
    setup_rest_api_routes(app)

    if settings.PENNSIEVE.PENNSIEVE_ENABLED:
        pennsieve.setup(app, settings.PENNSIEVE)

    set_app_default_http_error_handlers(app)

    return app
