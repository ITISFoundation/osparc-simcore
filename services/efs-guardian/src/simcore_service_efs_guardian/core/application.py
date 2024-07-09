import logging

from fastapi import FastAPI

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    APP_STARTED_DISABLED_BANNER_MSG,
)
from ..api.rest.routes import setup_api_routes
from ..api.rpc.routes import setup_rpc_routes
from ..services.efs_manager_setup import setup as setup_efs_manager
from ..services.modules.rabbitmq import setup as setup_rabbitmq
from .settings import ApplicationSettings

logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings) -> FastAPI:
    logger.info("app settings: %s", settings.json(indent=1))

    app = FastAPI(
        debug=settings.EFS_GUARDIAN_DEBUG,
        title=APP_NAME,
        description="Service to monitor and manage elastic file system",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )
    # STATE
    app.state.settings = settings
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    # PLUGINS SETUP
    setup_rabbitmq(app)

    setup_api_routes(app)
    setup_rpc_routes(app)

    setup_efs_manager(app)

    # EVENTS
    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
        if any(
            s is None
            for s in [
                settings.EFS_GUARDIAN_AWS_EFS_SETTINGS,
            ]
        ):
            print(APP_STARTED_DISABLED_BANNER_MSG, flush=True)  # noqa: T201

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
