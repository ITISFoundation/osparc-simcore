import logging
from typing import Any, Callable, Coroutine

from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method

from .._meta import API_VTAG, __version__
from ..api import main_router
from ..models.domains.shared_store import SharedStore
from ..models.schemas.application_health import ApplicationHealth
from ..modules.directory_watcher import setup_directory_watcher
from .docker_logs import setup_background_log_fetcher
from .error_handlers import http_error_handler
from .errors import BaseDynamicSidecarError
from .rabbitmq import setup_rabbitmq
from .remote_debug import setup as remote_debug_setup
from .settings import DynamicSidecarSettings
from .shared_handlers import on_shutdown_handler
from .utils import login_registry, volumes_fix_permissions

logger = logging.getLogger(__name__)

#
# https://patorjk.com/software/taag/#p=display&f=AMC%20Tubes&t=DYSIDECAR
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

    dynamic_sidecar_settings = DynamicSidecarSettings.create_from_envs()

    logging.basicConfig(level=dynamic_sidecar_settings.loglevel)
    logging.root.setLevel(dynamic_sidecar_settings.loglevel)
    logger.debug(dynamic_sidecar_settings.json(indent=2))

    application = FastAPI(
        debug=dynamic_sidecar_settings.DEBUG,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
    )
    override_fastapi_openapi_method(application)

    # store "settings"  and "shared_store" for later usage
    application.state.settings = dynamic_sidecar_settings
    application.state.shared_store = SharedStore(settings=dynamic_sidecar_settings)  # type: ignore
    # used to keep track of the health of the application
    # also will be used in the /health endpoint
    application.state.application_health = ApplicationHealth()

    # enable debug if required
    if dynamic_sidecar_settings.is_development_mode:
        remote_debug_setup(application)

    if dynamic_sidecar_settings.RABBIT_SETTINGS:
        setup_rabbitmq(application)
        # requires rabbitmq to be in place
        setup_background_log_fetcher(application)

    # add routing paths
    application.include_router(main_router)

    # error handlers
    application.add_exception_handler(BaseDynamicSidecarError, http_error_handler)

    # also sets up mounted_volumes
    setup_directory_watcher(application)

    def create_start_app_handler() -> Callable[[], Coroutine[Any, Any, None]]:
        async def on_startup() -> None:
            await login_registry(application.state.settings.REGISTRY_SETTINGS)
            await volumes_fix_permissions(application.state.mounted_volumes)

            print(WELCOME_MSG, flush=True)

        return on_startup

    def create_stop_app_handler() -> Callable[[], Coroutine[Any, Any, None]]:
        async def on_shutdown() -> None:
            await on_shutdown_handler(application)
            logger.info("shutdown cleanup completed")

        return on_shutdown

    application.add_event_handler("startup", create_start_app_handler())
    application.add_event_handler("shutdown", create_stop_app_handler())

    return application
