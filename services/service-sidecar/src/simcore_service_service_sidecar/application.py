from fastapi import FastAPI
from .settings import ServiceSidecarSettings
from .remote_debug import setup as remote_debug_setup
from .storage import AsyncStore
from .api import main_router
from .models import ApplicationHealth


def assemble_application() -> FastAPI:
    """
    Creates the application from using the env vars as a context
    Also stores inside the state all instances of classes
    needed in other requests and used to share data.
    """

    service_sidecar_settings = ServiceSidecarSettings.create()

    application = FastAPI(debug=service_sidecar_settings.debug)

    # store "settings"  and "async_store" for later usage
    application.state.settings = service_sidecar_settings
    application.state.async_store = AsyncStore(settings=service_sidecar_settings)
    # used to keep track of the health of the application
    # also will be used in the /health endpoint
    application.state.application_health = ApplicationHealth()

    # enable debug if required
    if service_sidecar_settings.is_development_mode:
        remote_debug_setup(application)

    # add routing paths
    application.include_router(main_router)

    return application