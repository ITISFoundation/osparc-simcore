import logging

from fastapi import FastAPI
from fastapi_pagination import add_pagination as setup_fastapi_pagination
from servicelib.fastapi.openapi import override_fastapi_openapi_method

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.routes import setup_api_routes
from ..modules.db import setup as setup_db
from ..modules.rabbitmq import setup as setup_rabbitmq
from ..modules.redis import setup as setup_redis
from ..resource_tracker import setup as setup_resource_tracker
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _set_exception_handlers(app: FastAPI):
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    # director-v2 core.errors mappend into HTTP errors
    app.add_exception_handler(
        ProjectNotFoundError,
        make_http_error_handler_for_exception(
            status.HTTP_404_NOT_FOUND, ProjectNotFoundError
        ),
    )
    app.add_exception_handler(
        PipelineNotFoundError,
        make_http_error_handler_for_exception(
            status.HTTP_404_NOT_FOUND, PipelineNotFoundError
        ),
    )
    app.add_exception_handler(
        ClusterNotFoundError,
        make_http_error_handler_for_exception(
            status.HTTP_404_NOT_FOUND, ClusterNotFoundError
        ),
    )
    app.add_exception_handler(
        ClusterAccessForbiddenError,
        make_http_error_handler_for_exception(
            status.HTTP_403_FORBIDDEN, ClusterAccessForbiddenError
        ),
    )

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


def create_app(settings: ApplicationSettings) -> FastAPI:
    _logger.info("app settings: %s", settings.json(indent=1))

    app = FastAPI(
        debug=settings.RESOURCE_USAGE_TRACKER_DEBUG,
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled, see below
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    # PLUGINS SETUP
    setup_api_routes(app)
    setup_fastapi_pagination(app)

    if settings.RESOURCE_USAGE_TRACKER_POSTGRES:
        setup_db(app)
    setup_redis(app)
    setup_rabbitmq(app)

    setup_resource_tracker(app)

    # EVENTS
    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    _set_exception_handlers(app)

    return app
