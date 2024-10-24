import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from servicelib.fastapi.tracing import setup_tracing
from servicelib.logging_utils import config_all_loggers

from .._meta import API_VERSION, API_VTAG, APP_NAME
from ..api.errors.http_error import http_error_handler
from ..api.errors.validation_error import http422_error_handler
from ..api.module_setup import setup_api
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

logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings | None = None) -> FastAPI:
    if settings is None:
        settings = ApplicationSettings.create_from_envs()
    assert settings  # nosec

    logging.basicConfig(level=settings.LOG_LEVEL.value)
    logging.root.setLevel(settings.LOG_LEVEL.value)
    config_all_loggers(
        log_format_local_dev_enabled=settings.DATCORE_ADAPTER_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.DATCORE_ADAPTER_LOG_FILTER_MAPPING,
    )

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
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )
    override_fastapi_openapi_method(app)

    app.state.settings = settings

    if app.state.settings.DATCORE_ADAPTER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)
    if app.state.settings.DATCORE_ADAPTER_TRACING:
        setup_tracing(
            app,
            app.state.settings.DATCORE_ADAPTER_TRACING,
            APP_NAME,
        )

    # events
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))
    app.add_event_handler("shutdown", on_shutdown)

    # Routing
    setup_api(app)

    if settings.PENNSIEVE.PENNSIEVE_ENABLED:
        pennsieve.setup(app, settings.PENNSIEVE)

    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)

    return app
