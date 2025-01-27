"""Main's application module for simcore_service_storage service

Functions to create, setup and run an aiohttp application provided a settingsuration object
"""

import logging
from typing import Final

from common_library.basic_types import BootModeEnum
from fastapi import FastAPI
from servicelib.aiohttp.dev_error_logger import setup_dev_error_logger
from servicelib.aiohttp.monitoring import setup_monitoring
from servicelib.aiohttp.profiler_middleware import profiling_middleware
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import setup_tracing

from .._meta import API_VERSION, API_VTAG, APP_NAME, APP_STARTED_BANNER_MSG, VERSION
from ..api.rest.utils import dsm_exception_handler
from ..dsm import setup_dsm
from ..dsm_cleaner import setup_dsm_cleaner
from ..modules.db.db import setup_db
from ..modules.long_running_tasks import setup_rest_api_long_running_tasks
from ..modules.redis import setup_redis
from ..modules.s3 import setup_s3
from ..routes import setup_rest_api_routes
from .settings import ApplicationSettings

_ACCESS_LOG_FORMAT: Final[
    str
] = '%a %t "%r" %s %b [%Dus] "%{Referer}i" "%{User-Agent}i"'

_LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
_NOISY_LOGGERS = (
    "aiobotocore",
    "aio_pika",
    "aiormq",
    "botocore",
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

    if settings.STORAGE_TRACING:
        setup_tracing(
            app,
            settings.STORAGE_TRACING,
            APP_NAME,
        )

    setup_db(app)
    setup_s3(app)

    setup_rest_api_long_running_tasks(app)
    setup_rest_api_routes(app)

    setup_dsm(app)
    if settings.STORAGE_CLEANER_INTERVAL_S:
        setup_redis(app)
        setup_dsm_cleaner(app)

    app.middlewares.append(dsm_exception_handler)

    if settings.STORAGE_PROFILING:
        app.middlewares.append(profiling_middleware)

    if settings.LOG_LEVEL == "DEBUG":
        setup_dev_error_logger(app)

    if settings.STORAGE_MONITORING_ENABLED:
        setup_monitoring(app, APP_NAME, version=f"{VERSION}")

    return app


def run(settings: ApplicationSettings, app: FastAPI | None = None):
    _logger.debug("Serving application ")
    if not app:
        app = create_app(settings)

    async def welcome_banner(_app: FastAPI):
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    app.on_startup.append(welcome_banner)

    web.run_app(
        app,
        host=settings.STORAGE_HOST,
        port=settings.STORAGE_PORT,
        access_log_format=_ACCESS_LOG_FORMAT,
    )
