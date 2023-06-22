import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi_pagination import add_pagination
from httpx import HTTPStatusError
from models_library.basic_types import BootModeEnum
from servicelib.logging_utils import config_all_loggers
from starlette import status
from starlette.exceptions import HTTPException

from .._meta import API_VERSION, API_VTAG
from ..api.errors.http_error import (
    http_error_handler,
    make_http_error_handler_for_exception,
)
from ..api.errors.httpx_client_error import httpx_client_error_handler
from ..api.errors.validation_error import http422_error_handler
from ..api.root import create_router
from ..api.routes.health import router as health_router
from ..plugins import catalog, director_v2, remote_debug, storage, webserver
from .events import create_start_app_handler, create_stop_app_handler
from .openapi import override_openapi_method, use_route_names_as_operation_ids
from .redoc import create_redoc_handler
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def init_app(settings: ApplicationSettings | None = None) -> FastAPI:
    if settings is None:
        settings = ApplicationSettings.create_from_envs()
    assert settings  # nosec

    logging.basicConfig(level=settings.log_level)
    logging.root.setLevel(settings.log_level)
    config_all_loggers(settings.API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED)
    _logger.debug("App settings:\n%s", settings.json(indent=2))

    # creates app instance
    app = FastAPI(
        debug=settings.debug,
        title="osparc.io web API",
        description="osparc-simcore public web API specifications",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled, see below
    )
    override_openapi_method(app)
    add_pagination(app)

    app.state.settings = settings

    # setup modules
    if settings.SC_BOOT_MODE == BootModeEnum.DEBUG:
        remote_debug.setup(app)

    if settings.API_SERVER_WEBSERVER:
        webserver.setup(app, settings.API_SERVER_WEBSERVER)

    if settings.API_SERVER_CATALOG:
        catalog.setup(app, settings.API_SERVER_CATALOG)

    if settings.API_SERVER_STORAGE:
        storage.setup(app, settings.API_SERVER_STORAGE)

    if settings.API_SERVER_DIRECTOR_V2:
        director_v2.setup(app, settings.API_SERVER_DIRECTOR_V2)

    # setup app
    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))

    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    app.add_exception_handler(HTTPStatusError, httpx_client_error_handler)

    # SEE https://docs.python.org/3/library/exceptions.html#exception-hierarchy
    app.add_exception_handler(
        NotImplementedError,
        make_http_error_handler_for_exception(
            NotImplementedError, status.HTTP_501_NOT_IMPLEMENTED
        ),
    )
    app.add_exception_handler(
        Exception,
        make_http_error_handler_for_exception(
            Exception,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            override_detail_message="Internal error"
            if settings.SC_BOOT_MODE == BootModeEnum.DEBUG
            else None,
        ),
    )

    # routing

    # healthcheck at / and at /VTAG/
    app.include_router(health_router)

    # docs
    redoc_html = create_redoc_handler(app)
    app.add_route("/doc", redoc_html, name="redoc_html", include_in_schema=False)

    # api under /v*
    api_router = create_router(settings)
    app.include_router(api_router, prefix=f"/{API_VTAG}")

    # NOTE: cleanup all OpenAPIs https://github.com/ITISFoundation/osparc-simcore/issues/3487
    use_route_names_as_operation_ids(app)
    return app
