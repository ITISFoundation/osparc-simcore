import logging
import time
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from models_library.basic_types import BootModeEnum
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.profiler_middleware import ProfilerMiddleware
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from servicelib.logging_utils import config_all_loggers
from starlette import status
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.errors.http_error import (
    http_error_handler,
    make_http_error_handler_for_exception,
)
from ..api.errors.validation_error import http422_error_handler
from ..api.root import router as api_router
from ..api.routes.health import router as health_router
from ..services.function_services import setup_function_services
from .events import create_start_app_handler, create_stop_app_handler
from .settings import ApplicationSettings

logger = logging.getLogger(__name__)


def init_app(settings: ApplicationSettings | None = None) -> FastAPI:
    if settings is None:
        settings = ApplicationSettings.create_from_envs()
    assert settings  # nosec
    logging.basicConfig(level=settings.CATALOG_LOG_LEVEL.value)
    logging.root.setLevel(settings.CATALOG_LOG_LEVEL.value)
    config_all_loggers(settings.CATALOG_LOG_FORMAT_LOCAL_DEV_ENABLED)
    logger.debug(settings.json(indent=2))

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

    # PLUGIN SETUP
    setup_function_services(app)

    if app.state.settings.CATALOG_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    if app.state.settings.CATALOG_PROFILING:
        app.add_middleware(ProfilerMiddleware)

    # EVENTS
    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("startup", create_start_app_handler(app))

    app.add_event_handler("shutdown", create_stop_app_handler(app))
    app.add_event_handler("shutdown", _on_shutdown)

    # ERROR HANDLERS
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    # SEE https://docs.python.org/3/library/exceptions.html#exception-hierarchy
    app.add_exception_handler(
        NotImplementedError,
        make_http_error_handler_for_exception(
            status.HTTP_501_NOT_IMPLEMENTED, NotImplementedError
        ),
    )
    app.add_exception_handler(
        Exception,
        make_http_error_handler_for_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR, Exception
        ),
    )

    # ROUTING
    # healthcheck at / and at /v0/
    app.include_router(health_router)

    # api under /v*
    app.include_router(api_router, prefix=f"/{API_VTAG}")

    # MIDDLEWARES
    # middleware to time requests (ONLY for development)
    if settings.SC_BOOT_MODE != BootModeEnum.PRODUCTION:

        async def _add_process_time_header(request: Request, call_next: Callable):
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            return response

        app.add_middleware(BaseHTTPMiddleware, dispatch=_add_process_time_header)

    # gzip middleware
    app.add_middleware(GZipMiddleware)

    return app
