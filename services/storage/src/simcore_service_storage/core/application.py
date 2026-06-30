"""Main's application module for simcore_service_storage service

Functions to create, setup and run an aiohttp application provided a settingsuration object
"""

from celery_library.basic_types import BootServerMode
from common_library.basic_types import BootModeEnum
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_lifespan_manager import LifespanManager
from fastapi_pagination import add_pagination
from servicelib.fastapi import timing_middleware
from servicelib.fastapi.cancellation_middleware import RequestCancellationMiddleware
from servicelib.fastapi.httpx_client import configure_httpx_client
from servicelib.fastapi.lifespan_utils import configure_app_lifespan
from servicelib.fastapi.monitoring import (
    configure_prometheus_instrumentation,
)
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.profiler import ProfilerMiddleware
from servicelib.fastapi.tracing import (
    configure_fastapi_app_tracing,
)
from servicelib.tracing import TracingConfig
from starlette.middleware.base import BaseHTTPMiddleware

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTING_BANNER_MSG,
    get_started_banner,
)
from ..api.rest.routes import setup_rest_api_routes
from ..dsm import configure_dsm_provider
from ..dsm_cleaner import configure_dsm_cleaner
from ..exceptions.handlers import set_exception_handlers
from ..modules.celery import configure_celery_task_manager
from ..modules.db import configure_db
from ..modules.rabbitmq import configure_rabbitmq_client
from ..modules.redis import configure_redis_clients
from ..modules.s3 import configure_s3_client
from .settings import ApplicationSettings


def _configure_app(
    app: FastAPI,
    app_lifespan: LifespanManager,
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> None:
    # Setup httpx client lifecycle
    configure_httpx_client(
        app_lifespan,
        tracing_config=tracing_config,
    )

    # Core infrastructure: database
    configure_db(app_lifespan)

    # S3 client for storage operations
    configure_s3_client(app_lifespan)

    # Redis for caching and locks
    configure_redis_clients(app_lifespan, settings=settings.STORAGE_REDIS)

    # RabbitMQ for messaging
    configure_rabbitmq_client(app_lifespan, settings=settings.STORAGE_RABBITMQ)

    # Celery task manager (depends on Redis)
    if settings.STORAGE_CELERY:
        configure_celery_task_manager(app_lifespan, settings.STORAGE_CELERY)

    # DSM provider (data storage manager)
    configure_dsm_provider(app_lifespan)

    # Monitoring and tracing
    if settings.STORAGE_MONITORING_ENABLED:
        configure_prometheus_instrumentation(app, app_lifespan)

    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(app, app_lifespan, tracing_config=tracing_config)

    match settings.STORAGE_BOOT_SERVER_MODE:
        case BootServerMode.AS_REST_API_SERVER:
            if settings.STORAGE_CLEANER_INTERVAL_S:
                configure_dsm_cleaner(app_lifespan)
            # Setup routes and exception handlers (outside the lifespan context)

            # Configure middleware (in reverse order due to how middleware is applied)
            if settings.STORAGE_PROFILING:
                app.add_middleware(ProfilerMiddleware)

            if settings.SC_BOOT_MODE != BootModeEnum.PRODUCTION:
                # middleware to time requests (ONLY for development)
                app.add_middleware(BaseHTTPMiddleware, dispatch=timing_middleware.add_process_time_header)

            app.add_middleware(GZipMiddleware)
            app.add_middleware(RequestCancellationMiddleware)

            setup_rest_api_routes(app, API_VTAG)
            set_exception_handlers(app)


def create_app(settings: ApplicationSettings, tracing_config: TracingConfig) -> FastAPI:
    with configure_app_lifespan(
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=get_started_banner(settings.STORAGE_BOOT_SERVER_MODE),
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
        app = FastAPI(
            debug=settings.SC_BOOT_MODE in {BootModeEnum.DEBUG, BootModeEnum.DEVELOPMENT, BootModeEnum.LOCAL},
            title=APP_NAME,
            description="Service that manages osparc storage backend",
            version=API_VERSION,
            openapi_url=f"/api/{API_VTAG}/openapi.json",
            docs_url="/dev/doc",
            redoc_url=None,  # default disabled
            lifespan=app_lifespan,
        )
        override_fastapi_openapi_method(app)
        add_pagination(app)

        # STATE
        app.state.settings = settings
        app.state.tracing_config = tracing_config

        _configure_app(app, app_lifespan, settings, tracing_config)

    return app
