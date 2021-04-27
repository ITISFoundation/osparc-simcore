import logging

from fastapi import FastAPI

from .._meta import api_vtag
from ..api import main_router
from ..models.domains.shared_store import SharedStore
from ..models.schemas.application_health import ApplicationHealth
from .remote_debug import setup as remote_debug_setup
from .settings import DynamicSidecarSettings
from .shared_handlers import on_shutdown_handler

logger = logging.getLogger(__name__)


def assemble_application() -> FastAPI:
    """
    Creates the application from using the env vars as a context
    Also stores inside the state all instances of classes
    needed in other requests and used to share data.
    """

    dynamic_sidecar_settings = DynamicSidecarSettings.create()

    logging.basicConfig(level=dynamic_sidecar_settings.loglevel)
    logging.root.setLevel(dynamic_sidecar_settings.loglevel)
    logger.debug(dynamic_sidecar_settings.json(indent=2))

    application = FastAPI(
        debug=dynamic_sidecar_settings.debug,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        docs_url="/dev/doc",
    )

    # store "settings"  and "shared_store" for later usage
    application.state.settings = dynamic_sidecar_settings
    application.state.shared_store = SharedStore(settings=dynamic_sidecar_settings)  # type: ignore
    # used to keep track of the health of the application
    # also will be used in the /health endpoint
    application.state.application_health = ApplicationHealth()

    # enable debug if required
    if dynamic_sidecar_settings.is_development_mode:
        remote_debug_setup(application)

    # add routing paths
    application.include_router(main_router)

    # setting up handler for lifecycle
    async def on_shutdown() -> None:
        await on_shutdown_handler(application)
        logger.info("shutdown cleanup completed")

    application.add_event_handler("shutdown", on_shutdown)

    return application
