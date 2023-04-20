import logging
from asyncio import Lock

from fastapi import FastAPI
from models_library.basic_types import BootModeEnum
from servicelib.async_utils import cancel_sequential_workers
from servicelib.fastapi import long_running_tasks
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.logging_utils import config_all_loggers
from simcore_sdk.node_ports_common.exceptions import NodeNotFound

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME, SUMMARY, __version__
from ..api import main_router
from ..models.schemas.application_health import ApplicationHealth
from ..models.shared_store import SharedStore, setup_shared_store
from ..modules.attribute_monitor import setup_attribute_monitor
from ..modules.mounted_fs import MountedVolumes, setup_mounted_fs
from ..modules.outputs import setup_outputs
from ..modules.volume_files import (
    create_agent_file_on_all_volumes,
    create_hidden_file_on_all_volumes,
)
from .docker_compose_utils import docker_compose_down
from .docker_logs import setup_background_log_fetcher
from .error_handlers import http_error_handler, node_not_found_error_handler
from .errors import BaseDynamicSidecarError
from .rabbitmq import setup_rabbitmq
from .remote_debug import setup as remote_debug_setup
from .settings import ApplicationSettings
from .utils import login_registry

logger = logging.getLogger(__name__)

#
# https://patorjk.com/software/taag/#p=display&f=AMC%20Tubes&t=DYSIDECAR
#

APP_STARTED_BANNER_MSG = r"""
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

APP_FINISHED_BANNER_MSG = "{:=^100}".format("🎉 App shutdown completed 🎉")


class AppState:
    """Exposes states of an initialized app

    Provides a stricter control on the read/write access
    of the different app.state fields during the app's lifespan
    """

    _STATES = {
        "settings": ApplicationSettings,
        "mounted_volumes": MountedVolumes,
        "shared_store": SharedStore,
    }

    def __init__(self, initialized_app: FastAPI):
        # Ensures states are initialized upon construction
        errors = [
            f"app.state.{name}"
            for name, type_ in AppState._STATES.items()
            if not isinstance(getattr(initialized_app.state, name, None), type_)
        ]
        if errors:
            raise ValueError(
                f"These app states were not properly initialized: {errors}"
            )

        self._app = initialized_app

    @property
    def settings(self) -> ApplicationSettings:
        assert isinstance(self._app.state.settings, ApplicationSettings)  # nosec
        return self._app.state.settings

    @property
    def mounted_volumes(self) -> MountedVolumes:
        assert isinstance(self._app.state.mounted_volumes, MountedVolumes)  # nosec
        return self._app.state.mounted_volumes

    @property
    def _shared_store(self) -> SharedStore:
        assert isinstance(self._app.state.shared_store, SharedStore)  # nosec
        return self._app.state.shared_store

    @property
    def compose_spec(self) -> str | None:
        return self._shared_store.compose_spec


def setup_logger(settings: ApplicationSettings):
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
    logging.basicConfig(level=settings.log_level)
    logging.root.setLevel(settings.log_level)
    config_all_loggers()


def create_base_app() -> FastAPI:
    # settings
    settings = ApplicationSettings.create_from_envs()
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

    long_running_tasks.server.setup(app)

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

    setup_shared_store(app)
    app.state.application_health = ApplicationHealth()

    if app.state.settings.SC_BOOT_MODE == BootModeEnum.DEBUG:
        remote_debug_setup(app)

    if app.state.settings.RABBIT_SETTINGS:
        setup_rabbitmq(app)
        setup_background_log_fetcher(app)

    # also sets up mounted_volumes
    setup_mounted_fs(app)
    setup_outputs(app)

    setup_attribute_monitor(app)

    # ERROR HANDLERS  ------------
    app.add_exception_handler(NodeNotFound, node_not_found_error_handler)
    app.add_exception_handler(BaseDynamicSidecarError, http_error_handler)

    # EVENTS ---------------------

    async def _on_startup() -> None:
        app.state.container_restart_lock = Lock()

        app_state = AppState(app)
        await login_registry(app_state.settings.REGISTRY_SETTINGS)
        await create_hidden_file_on_all_volumes(app_state.mounted_volumes)
        await create_agent_file_on_all_volumes(app_state.mounted_volumes)
        # STARTED
        print(APP_STARTED_BANNER_MSG, flush=True)

    async def _on_shutdown() -> None:
        app_state = AppState(app)
        if docker_compose_yaml := app_state.compose_spec:
            logger.info("Removing spawned containers")

            result = await docker_compose_down(docker_compose_yaml, app.state.settings)

            logger.log(
                logging.INFO if result.success else logging.ERROR,
                "Removed spawned containers:\n%s",
                result.message,
            )

        await cancel_sequential_workers()

        # FINISHED
        print(APP_FINISHED_BANNER_MSG, flush=True)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
