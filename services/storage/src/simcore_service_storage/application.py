""" Main's application module for simcore_service_storage service

    Functions to create, setup and run an aiohttp application provided a settingsuration object
"""
import logging
from typing import Optional

from aiohttp import web
from servicelib.aiohttp.application import APP_CONFIG_KEY, create_safe_application
from servicelib.aiohttp.dev_error_logger import setup_dev_error_logger
from servicelib.aiohttp.monitoring import setup_monitoring
from servicelib.aiohttp.tracing import setup_tracing

from ._meta import WELCOME_MSG, app_name, version
from .db import setup_db
from .dsm import setup_dsm
from .dsm_cleaner import setup_dsm_cleaner
from .rest import setup_rest
from .s3 import setup_s3
from .settings import Settings
from .utils_handlers import dsm_exception_handler

log = logging.getLogger(__name__)


def create(settings: Settings) -> web.Application:
    log.debug(
        "Initializing app with settings:\n%s",
        settings.json(indent=2, sort_keys=True),
    )

    # TODO: tmp using {} until webserver is also pydantic-compatible
    app = create_safe_application(None)
    app[APP_CONFIG_KEY] = settings

    if settings.STORAGE_TRACING:
        setup_tracing(
            app,
            service_name="simcore_service_storage",
            host=settings.STORAGE_HOST,
            port=settings.STORAGE_PORT,
            jaeger_base_url=f"{settings.STORAGE_TRACING.TRACING_ZIPKIN_ENDPOINT}",
            skip_routes=None,
        )

    if settings.STORAGE_POSTGRES:
        setup_db(app)  # -> postgres service
    if settings.STORAGE_S3:
        setup_s3(app)  # -> minio service

    setup_rest(app)

    if settings.STORAGE_POSTGRES and settings.STORAGE_S3:
        setup_dsm(app)  # core subsystem. Needs s3 and db setups done
        if settings.STORAGE_CLEANER_INTERVAL_S:
            setup_dsm_cleaner(app)

        app.middlewares.append(dsm_exception_handler)

    if settings.LOG_LEVEL == "DEBUG":
        setup_dev_error_logger(app)

    if settings.STORAGE_MONITORING_ENABLED:
        setup_monitoring(app, app_name, version=f"{version}")

    return app


def run(settings: Settings, app: Optional[web.Application] = None):
    log.debug("Serving application ")
    if not app:
        app = create(settings)

    async def welcome_banner(_app: web.Application):
        print(WELCOME_MSG, flush=True)

    app.on_startup.append(welcome_banner)

    web.run_app(app, host=settings.STORAGE_HOST, port=settings.STORAGE_PORT)
