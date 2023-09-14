import json
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
from ..services import catalog, director_v2, remote_debug, storage, webserver
from .events import create_start_app_handler, create_stop_app_handler
from .openapi import override_openapi_method, use_route_names_as_operation_ids
from .settings import ApplicationSettings

_settings: ApplicationSettings = ApplicationSettings.create_from_envs()

if _settings.API_SERVER_DEV_FEATURES_ENABLED:
    from pyinstrument import Profiler
    from starlette.requests import Request


_logger = logging.getLogger(__name__)


def _generate_response_headers(content: bytes) -> list[tuple[bytes, bytes]]:
    headers: dict = dict()
    headers[b"content-length"] = str(len(content)).encode("utf8")
    headers[b"content-type"] = b"application/json"
    return list(headers.items())


class ApiServerProfilerMiddleware:
    """Following
    https://www.starlette.io/middleware/#cleanup-and-error-handling
    https://www.starlette.io/middleware/#reusing-starlette-components
    https://fastapi.tiangolo.com/advanced/middleware/#advanced-middleware
    """

    def __init__(self, app: FastAPI):
        self._app: FastAPI = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        profiler = Profiler(async_mode="enabled")
        request: Request = Request(scope)
        headers = dict(request.headers)
        if "x-profile-api-server" in headers:
            headers.pop("x-profile-api-server")
            scope["headers"] = [
                (k.encode("utf8"), v.encode("utf8")) for k, v in headers.items()
            ]
            profiler.start()

        async def send_wrapper(message):
            if profiler.is_running:
                profiler.stop()
            if profiler.last_session:
                body: bytes = json.dumps(
                    {"profile": profiler.output_text(unicode=True, color=True)}
                ).encode("utf8")
                if message["type"] == "http.response.start":
                    message["headers"] = _generate_response_headers(body)
                elif message["type"] == "http.response.body":
                    message["body"] = body
            await send(message)

        await self._app(scope, receive, send_wrapper)


def _label_info_with_state(title: str, version: str):
    labels = []
    if _settings.API_SERVER_DEV_FEATURES_ENABLED:
        labels.append("dev")

    if _settings.debug:
        labels.append("debug")

    if suffix_label := "+".join(labels):
        title += f" ({suffix_label})"
        version += f"-{suffix_label}"

    return title, version


def init_app() -> FastAPI:
    assert isinstance(_settings, ApplicationSettings)  # nosec

    logging.basicConfig(level=_settings.log_level)
    logging.root.setLevel(_settings.log_level)
    config_all_loggers(_settings.API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED)
    _logger.debug("App _settings:\n%s", _settings.json(indent=2))

    # Labeling
    title = "osparc.io web API"
    version = API_VERSION
    description = "osparc-simcore public API specifications"
    title, version = _label_info_with_state(title, version)

    # creates app instance
    app = FastAPI(
        debug=_settings.debug,
        title=title,
        description=description,
        version=version,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled, see below
    )
    override_openapi_method(app)
    add_pagination(app)

    app.state.settings = _settings

    # setup modules
    if _settings.SC_BOOT_MODE == BootModeEnum.DEBUG:
        remote_debug.setup(app)

    if _settings.API_SERVER_WEBSERVER:
        webserver.setup(app, _settings.API_SERVER_WEBSERVER)

    if _settings.API_SERVER_CATALOG:
        catalog.setup(app, _settings.API_SERVER_CATALOG)

    if _settings.API_SERVER_STORAGE:
        storage.setup(app, _settings.API_SERVER_STORAGE)

    if _settings.API_SERVER_DIRECTOR_V2:
        director_v2.setup(app, _settings.API_SERVER_DIRECTOR_V2)

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
            if _settings.SC_BOOT_MODE == BootModeEnum.DEBUG
            else None,
        ),
    )
    if _settings.API_SERVER_DEV_FEATURES_ENABLED:
        app.add_middleware(ApiServerProfilerMiddleware)

    # routing

    # healthcheck at / and at /VTAG/
    app.include_router(health_router)

    # api under /v*
    api_router = create_router(_settings)
    app.include_router(api_router, prefix=f"/{API_VTAG}")

    # NOTE: cleanup all OpenAPIs https://github.com/ITISFoundation/osparc-simcore/issues/3487
    use_route_names_as_operation_ids(app)
    return app
