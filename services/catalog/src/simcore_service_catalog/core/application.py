import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_lifespan_manager import LifespanManager, State
from models_library.basic_types import BootModeEnum
from servicelib.fastapi import timing_middleware
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.profiler import initialize_profiler
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from servicelib.fastapi.tracing import initialize_tracing
from simcore_service_catalog.core.background_tasks import setup_background_task
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
from ..api.rest.errors import setup_rest_exception_handlers
from ..api.rest.routes import setup_rest_routes
from ..api.rpc.routes import setup_rpc_routes
from ..infrastructure.director import director_lifespan
from ..infrastructure.postgres import postgres_lifespan
from ..infrastructure.rabbitmq import rabbitmq_lifespan
from ..repository.setup import setup_repository
from ..service.function_services import setup_function_services
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


async def _setup_banner(app: FastAPI) -> AsyncIterator[State]:
    # WARNING: this function is spied in the tests
    assert app
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    yield {}

    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


def _create_app_lifespan(settings: ApplicationSettings):
    assert settings  # nosec

    # app lifespan
    app_lifespan = LifespanManager()
    app_lifespan.add(_setup_banner)

    # - postgres lifespan
    postgres_lifespan.add(setup_repository)
    app_lifespan.include(postgres_lifespan)

    # - director lifespan
    app_lifespan.include(director_lifespan)

    # - rabbitmq lifespan
    rabbitmq_lifespan.add(setup_rpc_routes)
    app_lifespan.add(rabbitmq_lifespan)

    app_lifespan.add(setup_function_services)
    app_lifespan.add(setup_background_task)

    return app_lifespan


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
        lifespan=_create_app_lifespan(settings),
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings

    if settings.CATALOG_TRACING:
        initialize_tracing(app, settings.CATALOG_TRACING, APP_NAME)

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
    setup_rest_routes(app, vtag=API_VTAG)
    setup_rest_exception_handlers(app)

    return app
