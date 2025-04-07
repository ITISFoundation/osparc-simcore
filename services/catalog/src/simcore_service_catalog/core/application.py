import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_lifespan_manager import LifespanManager, State
from models_library.basic_types import BootModeEnum
from servicelib.fastapi import timing_middleware
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.postgres_lifespan import (
    PostgresLifespanStateKeys,
    postgres_lifespan,
)
from servicelib.fastapi.profiler import initialize_profiler
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from servicelib.fastapi.tracing import initialize_tracing
from starlette.middleware.base import BaseHTTPMiddleware

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_NAME,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.rest.routes import setup_rest_api_routes
from ..api.rpc.routes import setup_rpc_api_routes
from ..db.events import setup_database
from ..exceptions.handlers import setup_exception_handlers
from ..services.function_services import setup_function_services
from ..services.rabbitmq import setup_rabbitmq
from .events import (
    create_on_shutdown,
    create_on_startup,
    flush_finished_banner,
    flush_started_banner,
)
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


async def _main_setup(app: FastAPI) -> AsyncIterator[State]:
    flush_started_banner()

    settings: ApplicationSettings = app.state.settings

    yield {
        PostgresLifespanStateKeys.POSTGRES_SETTINGS: settings.CATALOG_POSTGRES,
    }

    flush_finished_banner()


def _create_app_lifespan():
    # app lifespan
    app_lifespan = LifespanManager()
    app_lifespan.add(_main_setup)

    # - postgres lifespan
    postgres_lifespan.add(setup_database)
    app_lifespan.include(postgres_lifespan)

    return app_lifespan


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
        lifespan=_create_app_lifespan(),
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings

    if settings.CATALOG_TRACING:
        initialize_tracing(app, settings.CATALOG_TRACING, APP_NAME)

    # STARTUP-EVENT
    app.add_event_handler("startup", create_on_startup(app))

    # PLUGIN SETUP
    setup_function_services(app)
    setup_rabbitmq(app)

    if settings.CATALOG_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    # MIDDLEWARES
    if settings.CATALOG_PROFILING:
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
    app.add_event_handler("shutdown", create_on_shutdown(app))

    # EXCEPTIONS
    setup_exception_handlers(app)

    return app
