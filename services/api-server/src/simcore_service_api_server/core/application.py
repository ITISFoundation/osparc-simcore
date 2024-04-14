import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi_pagination import add_pagination
from httpx import HTTPError as HttpxException
from models_library.basic_types import BootModeEnum
from servicelib.logging_utils import config_all_loggers
from starlette import status
from starlette.exceptions import HTTPException

from .._meta import API_VERSION, API_VTAG
from ..api.errors.custom_errors import CustomBaseError, custom_error_handler
from ..api.errors.http_error import (
    http_error_handler,
    make_http_error_handler_for_exception,
)
from ..api.errors.httpx_client_error import handle_httpx_client_exceptions
from ..api.errors.log_handling_error import log_handling_error_handler
from ..api.errors.validation_error import http422_error_handler
from ..api.root import create_router
from ..api.routes.health import router as health_router
from ..services import catalog, director_v2, storage, webserver
from ..services.log_streaming import LogDistributionBaseException
from ..services.rabbitmq import setup_rabbitmq
from ._prometheus_instrumentation import setup_prometheus_instrumentation
from .events import create_start_app_handler, create_stop_app_handler
from .openapi import override_openapi_method, use_route_names_as_operation_ids
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _label_info_with_state(settings: ApplicationSettings, title: str, version: str):
    labels = []
    if settings.API_SERVER_DEV_FEATURES_ENABLED:
        labels.append("dev")

    if settings.debug:
        labels.append("debug")

    if suffix_label := "+".join(labels):
        title += f" ({suffix_label})"
        version += f"-{suffix_label}"

    return title, version


def init_app(settings: ApplicationSettings | None = None) -> FastAPI:
    if settings is None:
        settings = ApplicationSettings.create_from_envs()
    assert settings  # nosec

    logging.basicConfig(level=settings.log_level)
    logging.root.setLevel(settings.log_level)
    config_all_loggers(settings.API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED)
    _logger.debug("App settings:\n%s", settings.json(indent=2))

    # Labeling
    title = "osparc.io web API"
    version = API_VERSION
    description = "osparc-simcore public API specifications"
    title, version = _label_info_with_state(settings, title, version)

    # creates app instance
    app = FastAPI(
        debug=settings.debug,
        title=title,
        description=description,
        version=version,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled, see below
    )
    override_openapi_method(app)
    add_pagination(app)

    app.state.settings = settings

    setup_rabbitmq(app)

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
    app.add_exception_handler(HttpxException, handle_httpx_client_exceptions)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    app.add_exception_handler(LogDistributionBaseException, log_handling_error_handler)
    app.add_exception_handler(CustomBaseError, custom_error_handler)

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
    if settings.API_SERVER_DEV_FEATURES_ENABLED:
        from ._profiler_middleware import ApiServerProfilerMiddleware

        app.add_middleware(ApiServerProfilerMiddleware)

    if app.state.settings.API_SERVER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    # routing

    # healthcheck at / and at /VTAG/
    app.include_router(health_router)

    # api under /v*
    api_router = create_router(settings)
    app.include_router(api_router, prefix=f"/{API_VTAG}")

    # NOTE: cleanup all OpenAPIs https://github.com/ITISFoundation/osparc-simcore/issues/3487
    use_route_names_as_operation_ids(app)
    return app
