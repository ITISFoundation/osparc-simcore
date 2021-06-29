import logging
from typing import Any, Callable, Coroutine

from fastapi import FastAPI

from .._meta import __version__, api_vtag
from ..api import main_router
from ..models.domains.shared_store import SharedStore
from ..models.schemas.application_health import ApplicationHealth
from .remote_debug import setup as remote_debug_setup
from .settings import DynamicSidecarSettings
from .shared_handlers import on_shutdown_handler
from .utils import login_registry

logger = logging.getLogger(__name__)

#
# https://patorjk.com/software/taag/#p=display&f=JS%20Stick%20Letters&t=API-server%0A
#

WELCOME_MSG = r"""
d ss    Ss   sS   sss. d d ss    d sss     sSSs. d s.   d ss.
S   ~o    S S   d      S S   ~o  S        S      S  ~O  S    b
S     b    S    Y      S S     b S       S       S   `b S    P
S     S    S      ss.  S S     S S sSSs  S       S sSSO S sS'
S     P    S         b S S     P S       S       S    O S   S
S    S     S         P S S    S  S        S      S    O S    S
P ss"      P    ` ss'  P P ss"   P sSSss   "sss' P    P P    P   {0}

""".format(
    f"v{__version__}"
)


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

    def create_start_app_handler(
        app: FastAPI,
    ) -> Callable[[], Coroutine[Any, Any, None]]:
        async def on_startup() -> None:
            await login_registry(app.state.settings.registry)
            print(WELCOME_MSG, flush=True)

        return on_startup

    # setting up handler for lifecycle
    async def on_shutdown() -> None:
        await on_shutdown_handler(application)
        logger.info("shutdown cleanup completed")

    application.add_event_handler("startup", create_start_app_handler(application))
    application.add_event_handler("shutdown", on_shutdown)

    return application
