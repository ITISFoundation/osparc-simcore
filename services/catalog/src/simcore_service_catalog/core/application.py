import logging

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from models_library.basic_types import BootModeEnum
from servicelib.fastapi import timing_middleware
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.profiler_middleware import ProfilerMiddleware
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from starlette.middleware.base import BaseHTTPMiddleware

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME, SUMMARY
from ..api import rest
from ..api.routes.health import router as health_router
from ..exceptions.handlers import setup_exception_handlers
from ..services.function_services import setup_function_services
from .events import create_on_shutdown, create_on_startup
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings | None = None) -> FastAPI:
    if settings is None:
        settings = ApplicationSettings.create_from_envs()

    assert settings  # nosec
    _logger.debug(settings.json(indent=2))

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

    # STARTUP-EVENT
    app.add_event_handler("startup", create_on_startup(app))

    # PLUGIN SETUP
    setup_function_services(app)

    if app.state.settings.CATALOG_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    # MIDDLEWARES
    if app.state.settings.CATALOG_PROFILING:
        app.add_middleware(ProfilerMiddleware)

    if settings.SC_BOOT_MODE != BootModeEnum.PRODUCTION:
        # middleware to time requests (ONLY for development)
        app.add_middleware(
            BaseHTTPMiddleware, dispatch=timing_middleware.add_process_time_header
        )

    app.add_middleware(GZipMiddleware)

    # ROUTES
    # healthcheck at / and at /v0/
    app.include_router(health_router)
    # api under /v*
    app.include_router(rest.v0_router, prefix=f"/{API_VTAG}")

    # SHUTDOWN-EVENT
    app.add_event_handler("shutdown", create_on_shutdown(app))

    # EXCEPTIONS
    setup_exception_handlers(app)

    return app
