import logging
from typing import Optional

from fastapi import FastAPI
from models_library.basic_types import BootModeEnum
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from simcore_sdk.node_ports_common.exceptions import NodeNotFound

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME, SUMMARY, __version__
from ..api import main_router
from ..models.schemas.application_health import ApplicationHealth
from ..models.shared_store import SharedStore
from ..modules.directory_watcher import setup_directory_watcher
from ..modules.mounted_fs import MountedVolumes, setup_mounted_fs
from .docker_compose_utils import docker_compose_down
from .docker_logs import setup_background_log_fetcher
from .error_handlers import http_error_handler, node_not_found_error_handler
from .errors import BaseDynamicSidecarError
from .rabbitmq import setup_rabbitmq
from .remote_debug import setup as remote_debug_setup
from .settings import DynamicSidecarSettings
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
P ss"      P    ` ss'  P P ss"   P sSSss   "sss' P    P P    P   {} 🚀

""".format(
    f"v{__version__}"
)

TSCHUESS_MSG = "{:=^100}".format("🎉 App shutdown completed 🎉")


class AppState:
    """Exposes states of an initialized app and defines
    the access rights for each state (i.e. read/write)
    during the app's lifetime
    """

    _STATES = {
        "settings": DynamicSidecarSettings,
        "mounted_volumes": MountedVolumes,
        "shared_store": SharedStore,
    }

    def __init__(self, initialized_app: FastAPI):
        # Ensures states are initialized upon construction
        errors = [
            "app.state.{name}"
            for name, type_ in AppState._STATES.items()
            if not isinstance(getattr(initialized_app.state, name, None), type_)
        ]
        if errors:
            raise ValueError(f"App states are not properly initialized. Found {errors}")

        self._app = initialized_app

    @property
    def settings(self) -> DynamicSidecarSettings:
        return self._app.state.settings  # type: ignore

    @property
    def mounted_volumes(self) -> MountedVolumes:
        return self._app.state.mounted_volumes  # type: ignore

    @property
    def _shared_store(self) -> SharedStore:
        return self._app.state.shared_store  # type: ignore

    @property
    def compose_spec(self) -> Optional[str]:
        return self._shared_store.compose_spec


def setup_logger(settings: DynamicSidecarSettings):
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
    logging.basicConfig(level=settings.log_level)
    logging.root.setLevel(settings.log_level)


def create_base_app() -> FastAPI:
    # settings
    settings = DynamicSidecarSettings.create_from_envs()
    setup_logger(settings)
    logger.debug(settings.json(indent=2))

    # minimal
    app = FastAPI(
        debug=settings.SC_BOOT_MODE.is_devel_mode(),
        title=PROJECT_NAME,
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        **get_common_oas_options(settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = settings

    app.include_router(main_router)
    return app


def create_app():
    """
    Creates the application from using the env vars as a context
    Also stores inside the state all instances of classes
    needed in other requests and used to share data.
    """

    app = create_base_app()

    # MODULES SETUP --------------

    app.state.shared_store = SharedStore()
    app.state.application_health = ApplicationHealth()

    if app.state.settings.SC_BOOT_MODE == BootModeEnum.DEBUG:
        remote_debug_setup(app)

    if app.state.settings.RABBIT_SETTINGS:
        setup_rabbitmq(app)
        setup_background_log_fetcher(app)

    # also sets up mounted_volumes
    setup_mounted_fs(app)
    setup_directory_watcher(app)

    # ERROR HANDLERS  ------------
    app.add_exception_handler(NodeNotFound, node_not_found_error_handler)
    app.add_exception_handler(BaseDynamicSidecarError, http_error_handler)

    # EVENTS ---------------------
    app_state = AppState(app)

    async def _on_startup() -> None:
        await login_registry(app_state.settings.REGISTRY_SETTINGS)
        await volumes_fix_permissions(app_state.mounted_volumes)
        # STARTED
        print(WELCOME_MSG, flush=True)

    async def _on_shutdown() -> None:
        if docker_compose_yaml := app_state.compose_spec:
            logger.info("Removing spawned containers")

            result = await docker_compose_down(
                docker_compose_yaml,
                app.state.settings,
                # NOTE: in the event of a SIGTERM, there is a limited time to cleanup
                timeout=app.state.settings.DYNAMIC_SIDECAR_DOCKER_COMPOSE_DOWN_TIMEOUT,
            )

            logger.log(
                logging.INFO if result.success else logging.ERROR,
                "Removed spawned containers:\n%s",
                result.decoded_stdout,
            )
        # FINISHED
        print(TSCHUESS_MSG, flush=True)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
