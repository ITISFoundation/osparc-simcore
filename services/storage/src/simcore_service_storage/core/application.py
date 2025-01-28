"""Main's application module for simcore_service_storage service

Functions to create, setup and run an aiohttp application provided a settingsuration object
"""

import logging

from common_library.basic_types import BootModeEnum
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from servicelib.fastapi import timing_middleware
from servicelib.fastapi.client_session import setup_client_session
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.profiler_middleware import ProfilerMiddleware
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from servicelib.fastapi.tracing import setup_tracing
from simcore_service_storage.api.rest.routes import setup_rest_api_routes
from starlette.middleware.base import BaseHTTPMiddleware

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
)
from ..api.rest.utils import set_exception_handlers
from ..dsm import setup_dsm
from ..dsm_cleaner import setup_dsm_cleaner
from ..modules.db.db import setup_db
from ..modules.long_running_tasks import setup_rest_api_long_running_tasks
from ..modules.redis import setup as setup_redis
from ..modules.s3 import setup_s3
from .settings import ApplicationSettings

_LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
_NOISY_LOGGERS = (
    "aio_pika",
    "aiobotocore",
    "aiormq",
    "botocore",
    "httpcore",
    "werkzeug",
)
_logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings) -> FastAPI:
    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + _LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)

    settings = ApplicationSettings.create_from_envs()
    _logger.info("app settings: %s", settings.model_dump_json(indent=1))

    app = FastAPI(
        debug=settings.SC_BOOT_MODE
        in [BootModeEnum.DEBUG, BootModeEnum.DEVELOPMENT, BootModeEnum.LOCAL],
        title=APP_NAME,
        description="Service to auto-scale swarm",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings

    setup_db(app)
    setup_s3(app)
    setup_client_session(app)

    setup_rest_api_long_running_tasks(app)
    setup_rest_api_routes(app, API_VTAG)
    set_exception_handlers(app)

    setup_dsm(app)
    if settings.STORAGE_CLEANER_INTERVAL_S:
        setup_redis(app)
        setup_dsm_cleaner(app)

    if settings.STORAGE_PROFILING:
        app.add_middleware(ProfilerMiddleware)

    if settings.SC_BOOT_MODE != BootModeEnum.PRODUCTION:
        # middleware to time requests (ONLY for development)
        app.add_middleware(
            BaseHTTPMiddleware, dispatch=timing_middleware.add_process_time_header
        )

    app.add_middleware(GZipMiddleware)

    if settings.STORAGE_TRACING:
        setup_tracing(app, settings.STORAGE_TRACING, APP_NAME)
    if settings.STORAGE_MONITORING_ENABLED:
        setup_prometheus_instrumentation(app)

    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
