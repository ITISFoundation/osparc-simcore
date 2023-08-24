import logging

from fastapi import FastAPI

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
)
from ..api.routes import setup_api_routes
from ..clusters_management_task import setup as setup_clusters_management
from ..modules.ec2 import setup as setup_ec2
from ..modules.rabbitmq import setup as setup_rabbitmq
from ..modules.redis import setup as setup_redis
from ..rpc.rpc_routes import setup_rpc_routes
from .settings import ApplicationSettings

logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings) -> FastAPI:
    logger.info("app settings: %s", settings.json(indent=1))

    app = FastAPI(
        debug=settings.CLUSTERS_KEEPER_DEBUG,
        title=APP_NAME,
        description="Service to keep external clusters alive",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )
    # STATE
    app.state.settings = settings
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    # PLUGINS SETUP
    setup_api_routes(app)
    setup_rabbitmq(app)
    setup_ec2(app)
    setup_redis(app)
    setup_clusters_management(app)
    setup_rpc_routes(app)

    # ERROR HANDLERS

    # EVENTS
    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
