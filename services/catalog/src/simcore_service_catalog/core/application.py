import logging

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from models_library.basic_types import BootModeEnum
from servicelib.fastapi import timing_middleware
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.profiler import initialize_profiler
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from servicelib.fastapi.tracing import initialize_tracing
from simcore_service_catalog.core.background_tasks import start_registry_sync_task
from simcore_service_catalog.infrastructure.director import setup_director
from simcore_service_catalog.infrastructure.postgres import setup_postgres_database
from starlette.middleware.base import BaseHTTPMiddleware

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.rest.routes import setup_rest_api_routes
from ..api.rpc.routes import setup_rpc_api_routes
from ..exceptions.handlers import setup_exception_handlers
from ..infrastructure.rabbitmq import setup_rabbitmq
from ..services.function_services import setup_function_services
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


def _flush_started_banner() -> None:
    # WARNING: this function is spied in the tests
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201


def _flush_finished_banner() -> None:
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


def create_app(settings: ApplicationSettings | None = None) -> FastAPI:
    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + _LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)

    if settings is None:
        settings = ApplicationSettings.create_from_envs()

    assert settings  # nosec
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
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings

    if settings.CATALOG_TRACING:
        initialize_tracing(app, settings.CATALOG_TRACING, APP_NAME)

    # STARTUP-EVENT
    app.add_event_handler("startup", _flush_started_banner)

    setup_postgres_database(app)
    setup_director(app)
    setup_function_services(app)
    setup_rabbitmq(app)

    app.add_event_handler("startup", start_registry_sync_task)

    if app.state.settings.CATALOG_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    # MIDDLEWARES
    if app.state.settings.CATALOG_PROFILING:
        initialize_profiler(app)

    if settings.SC_BOOT_MODE != BootModeEnum.PRODUCTION:
        # middleware to time requests (ONLY for development)
        app.add_middleware(
            BaseHTTPMiddleware, dispatch=timing_middleware.add_process_time_header
        )

    app.add_middleware(GZipMiddleware)

    # ROUTES
    setup_rest_api_routes(app, vtag=API_VTAG)
    setup_rpc_api_routes(app)

    # SHUTDOWN-EVENT
    app.add_event_handler("shutdown", _flush_finished_banner)

    # EXCEPTIONS
    setup_exception_handlers(app)

    return app
