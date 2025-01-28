""" Main's application module for simcore_service_storage service

    Functions to create, setup and run an aiohttp application provided a settingsuration object
"""

import logging
from typing import Final

from aiohttp import web
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from servicelib.aiohttp.dev_error_logger import setup_dev_error_logger
from servicelib.aiohttp.monitoring import setup_monitoring
from servicelib.aiohttp.profiler_middleware import profiling_middleware
from servicelib.aiohttp.tracing import setup_tracing
from settings_library.tracing import TracingSettings

from ._meta import APP_NAME, APP_STARTED_BANNER_MSG, VERSION
from .db import setup_db
from .dsm import setup_dsm
from .dsm_cleaner import setup_dsm_cleaner
from .long_running_tasks import setup_rest_api_long_running_tasks
from .redis import setup_redis
from .rest import setup_rest
from .s3 import setup_s3
from .settings import Settings
from .utils_handlers import dsm_exception_handler

_ACCESS_LOG_FORMAT: Final[
    str
] = '%a %t "%r" %s %b [%Dus] "%{Referer}i" "%{User-Agent}i"'

_LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
_NOISY_LOGGERS = (
    "aiobotocore",
    "aio_pika",
    "aiormq",
    "botocore",
    "sqlalchemy",
)
_logger = logging.getLogger(__name__)


def create(settings: Settings) -> web.Application:
    _logger.debug(
        "Initializing app with settings:\n%s",
        settings.model_dump_json(indent=2),
    )

    app = create_safe_application(None)
    app[APP_CONFIG_KEY] = settings
    # Tracing
    tracing_settings: TracingSettings | None = app[APP_CONFIG_KEY].STORAGE_TRACING
    if tracing_settings:
        setup_tracing(
            app,
            tracing_settings=tracing_settings,
            service_name=APP_NAME,
        )

    setup_db(app)
    setup_s3(app)

    setup_rest_api_long_running_tasks(app)
    setup_rest(app)

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

    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + _LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)

    return app


def run(settings: Settings, app: web.Application | None = None):
    _logger.debug("Serving application ")
    if not app:
        app = create(settings)

    async def welcome_banner(_app: web.Application):
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    app.on_startup.append(welcome_banner)

    web.run_app(
        app,
        host=settings.STORAGE_HOST,
        port=settings.STORAGE_PORT,
        access_log_format=_ACCESS_LOG_FORMAT,
    )
