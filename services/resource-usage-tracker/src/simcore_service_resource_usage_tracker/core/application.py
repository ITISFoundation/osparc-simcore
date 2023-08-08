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
from ..modules.prometheus import setup as setup_prometheus_api_client
from ..modules.rabbitmq import setup as setup_rabbitmq
from ..modules.redis import setup as setup_redis
from ..resource_tracker import setup as setup_resource_tracker
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


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

    # ERROR HANDLERS
    # ... add here ...
    setup_prometheus_api_client(app)
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

    return app
