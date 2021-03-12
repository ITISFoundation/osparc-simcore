import logging

from fastapi import FastAPI

from .api import main_router
from .models import ApplicationHealth
from .remote_debug import setup as remote_debug_setup
from .settings import ServiceSidecarSettings
from .shared_handlers import on_shutdown_handler
from .storage import SharedStore

logger = logging.getLogger(__name__)


def assemble_application() -> FastAPI:
    """
    Creates the application from using the env vars as a context
    Also stores inside the state all instances of classes
    needed in other requests and used to share data.
    """

    service_sidecar_settings = ServiceSidecarSettings.create()

    logging.basicConfig(level=service_sidecar_settings.loglevel)
    logging.root.setLevel(service_sidecar_settings.loglevel)
    logger.debug(service_sidecar_settings.json(indent=2))

    application = FastAPI(debug=service_sidecar_settings.debug)

    # store "settings"  and "shared_store" for later usage
    application.state.settings = service_sidecar_settings
    application.state.shared_store = SharedStore(settings=service_sidecar_settings)
    # used to keep track of the health of the application
    # also will be used in the /health endpoint
    application.state.application_health = ApplicationHealth()

    # enable debug if required
    if service_sidecar_settings.is_development_mode:
        remote_debug_setup(application)

    # add routing paths
    application.include_router(main_router)

    # setting up handler for lifecycle
    async def on_shutdown() -> None:
        await on_shutdown_handler(application)
        logger.info("shutdown cleanup completed")

    application.add_event_handler("shutdown", on_shutdown)

    return application
