import logging

from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from simcore_sdk.node_ports_common.exceptions import NodeNotFound

from .._meta import API_VTAG, __version__
from ..api import main_router
from ..models.domains.shared_store import SharedStore
from ..models.schemas.application_health import ApplicationHealth
from ..modules.directory_watcher import setup_directory_watcher
from ..modules.mounted_fs import setup_mounted_fs
from .docker_logs import setup_background_log_fetcher
from .error_handlers import http_error_handler, node_not_found_error_handler
from .errors import BaseDynamicSidecarError
from .rabbitmq import setup_rabbitmq
from .remote_debug import setup as remote_debug_setup
from .settings import DynamicSidecarSettings
from .shared_handlers import remove_the_compose_spec
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
P ss"      P    ` ss'  P P ss"   P sSSss   "sss' P    P P    P   {}

""".format(
    f"v{__version__}"
)


def setup_logger(settings: DynamicSidecarSettings):
    logging.basicConfig(level=settings.loglevel)
    logging.root.setLevel(settings.loglevel)


def assemble_application() -> FastAPI:
    """
    Creates the application from using the env vars as a context
    Also stores inside the state all instances of classes
    needed in other requests and used to share data.
    """
    settings = DynamicSidecarSettings.create_from_envs()
    setup_logger(settings)
    logger.debug(settings.json(indent=2))

    application = FastAPI(
        debug=settings.DEBUG,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
    )
    override_fastapi_openapi_method(application)

    application.state.settings = settings
    application.state.shared_store = SharedStore()
    application.state.application_health = ApplicationHealth()

    # ROUTES  --------------------
    application.include_router(main_router)

    # ERROR HANDLERS  ------------
    application.add_exception_handler(NodeNotFound, node_not_found_error_handler)
    application.add_exception_handler(BaseDynamicSidecarError, http_error_handler)

    # MODULES SETUP --------------

    if settings.is_development_mode:
        remote_debug_setup(application)

    if settings.RABBIT_SETTINGS:
        setup_rabbitmq(application)
        setup_background_log_fetcher(application)

    # also sets up mounted_volumes
    setup_mounted_fs(application)
    setup_directory_watcher(application)

    # EVENTS ---------------------
    async def _on_startup() -> None:
        await login_registry(application.state.settings.REGISTRY_SETTINGS)
        await volumes_fix_permissions(application.state.mounted_volumes)
        print(WELCOME_MSG, flush=True)

    async def _on_shutdown() -> None:
        logger.info("Going to remove spawned containers")
        result = await remove_the_compose_spec(
            shared_store=application.state.shared_store,
            settings=settings,
            command_timeout=settings.DYNAMIC_SIDECAR_DOCKER_COMPOSE_DOWN_TIMEOUT,
        )
        logger.info("Container removal did_succeed=%s\n%s", result[0], result[1])

        logger.info("shutdown cleanup completed")

    application.add_event_handler("startup", _on_startup)
    application.add_event_handler("shutdown", _on_shutdown)

    return application
