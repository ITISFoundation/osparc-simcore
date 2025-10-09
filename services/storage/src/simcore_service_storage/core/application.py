"""Main's application module for simcore_service_storage service

Functions to create, setup and run an aiohttp application provided a settingsuration object
"""

import logging

from common_library.basic_types import BootModeEnum
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_pagination import add_pagination
from servicelib.fastapi import timing_middleware
from servicelib.fastapi.cancellation_middleware import RequestCancellationMiddleware
from servicelib.fastapi.client_session import setup_client_session
from servicelib.fastapi.monitoring import (
    setup_prometheus_instrumentation,
)
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.profiler import ProfilerMiddleware
from servicelib.fastapi.tracing import (
    get_tracing_config,
    initialize_fastapi_app_tracing,
    setup_tracing,
)
from servicelib.tracing import TracingConfig
from starlette.middleware.base import BaseHTTPMiddleware

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    APP_WORKER_STARTED_BANNER_MSG,
)
from ..api.rest.routes import setup_rest_api_routes
from ..api.rpc.routes import setup_rpc_routes
from ..dsm import setup_dsm
from ..dsm_cleaner import setup_dsm_cleaner
from ..exceptions.handlers import set_exception_handlers
from ..modules.celery import setup_task_manager
from ..modules.db import setup_db
from ..modules.rabbitmq import setup as setup_rabbitmq
from ..modules.redis import setup as setup_redis
from ..modules.s3 import setup_s3
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def create_app(
    settings: ApplicationSettings, tracing_config: TracingConfig
) -> FastAPI:  # noqa: C901
    app = FastAPI(
        debug=settings.SC_BOOT_MODE
        in [BootModeEnum.DEBUG, BootModeEnum.DEVELOPMENT, BootModeEnum.LOCAL],
        title=APP_NAME,
        description="Service that manages osparc storage backend",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )
    override_fastapi_openapi_method(app)
    add_pagination(app)

    # STATE
    app.state.settings = settings
    app.state.tracing_config = tracing_config

    if tracing_config.tracing_enabled:
        setup_tracing(app, tracing_config)

    setup_db(app)
    setup_s3(app)
    setup_client_session(
        app,
        tracing_config=get_tracing_config(app),
    )

    if settings.STORAGE_CELERY:
        setup_task_manager(app, settings=settings.STORAGE_CELERY)

    if not settings.STORAGE_WORKER_MODE:
        setup_rabbitmq(app)
        setup_rpc_routes(app)

    setup_rest_api_routes(app, API_VTAG)
    set_exception_handlers(app)

    setup_redis(app)

    setup_dsm(app)
    if settings.STORAGE_CLEANER_INTERVAL_S and not settings.STORAGE_WORKER_MODE:
        setup_dsm_cleaner(app)

    if settings.STORAGE_PROFILING:
        app.add_middleware(ProfilerMiddleware)

    if settings.SC_BOOT_MODE != BootModeEnum.PRODUCTION:
        # middleware to time requests (ONLY for development)
        app.add_middleware(
            BaseHTTPMiddleware, dispatch=timing_middleware.add_process_time_header
        )

    app.add_middleware(GZipMiddleware)

    app.add_middleware(RequestCancellationMiddleware)

    if settings.STORAGE_MONITORING_ENABLED:
        setup_prometheus_instrumentation(app)

    if tracing_config.tracing_enabled:
        initialize_fastapi_app_tracing(app, tracing_config=tracing_config)

    async def _on_startup() -> None:
        if settings.STORAGE_WORKER_MODE:
            print(APP_WORKER_STARTED_BANNER_MSG, flush=True)  # noqa: T201
        else:
            print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
