""" Main's application module for simcore_service_storage service

    Functions to create, setup and run an aiohttp application provided a settingsuration object
"""
import logging
from typing import Optional

from aiohttp import web
from servicelib.aiohttp.application import APP_CONFIG_KEY, create_safe_application
from servicelib.aiohttp.monitoring import setup_monitoring
from servicelib.aiohttp.tracing import setup_tracing

from ._meta import WELCOME_MSG
from .db import setup_db
from .dsm import setup_dsm
from .rest import setup_rest
from .s3 import setup_s3
from .settings import Settings

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

    setup_db(app)  # -> postgres service
    setup_s3(app)  # -> minio service
    setup_dsm(app)  # core subsystem. Needs s3 and db setups done
    setup_rest(app)  # lastly, we expose API to the world

    if settings.STORAGE_MONITORING_ENABLED:
        setup_monitoring(app, "simcore_service_storage")

    return app


def run(settings: Settings, app: Optional[web.Application] = None):
    log.debug("Serving application ")
    if not app:
        app = create(settings)

    async def welcome_banner(_app: web.Application):
        print(WELCOME_MSG, flush=True)

    app.on_startup.append(welcome_banner)

    web.run_app(app, host=settings.STORAGE_HOST, port=settings.STORAGE_PORT)
