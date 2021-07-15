import logging
import time
from typing import Callable, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from starlette import status
from starlette.exceptions import HTTPException

from ..api.errors.http_error import (
    http_error_handler,
    make_http_error_handler_for_exception,
)
from ..api.errors.validation_error import http422_error_handler
from ..api.root import router as api_router
from ..api.routes.health import router as health_router
from ..meta import api_version, api_vtag
from ..services.frontend_services import setup_frontend_services
from .events import (
    create_start_app_handler,
    create_stop_app_handler,
    on_shutdown,
    on_startup,
)
from .settings import AppSettings, BootModeEnum

logger = logging.getLogger(__name__)


def init_app(settings: Optional[AppSettings] = None) -> FastAPI:
    if settings is None:
        settings = AppSettings.create_default()

    logging.basicConfig(level=settings.loglevel)
    logging.root.setLevel(settings.loglevel)

    app = FastAPI(
        debug=settings.debug,
        title="Components Catalog Service",
        description="Manages and maintains a **catalog** of all published components (e.g. macro-algorithms, scripts, etc)",
        version=api_version,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )

    logger.debug("App settings:%s", settings.json(indent=2))

    app.state.settings = settings

    setup_frontend_services(app)

    # events
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("startup", create_start_app_handler(app))

    app.add_event_handler("shutdown", on_shutdown)
    app.add_event_handler("shutdown", create_stop_app_handler(app))

    # exception handlers
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

    # Routing

    # healthcheck at / and at /v0/
    app.include_router(health_router)

    # api under /v*
    app.include_router(api_router, prefix=f"/{api_vtag}")

    # middleware to time requests (ONLY for development)
    if settings.boot_mode != BootModeEnum.PRODUCTION:

        @app.middleware("http")
        async def _add_process_time_header(request: Request, call_next: Callable):
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            return response

    # gzip middleware
    app.add_middleware(GZipMiddleware)

    return app
