import logging
from asyncio import Lock
from typing import Any, ClassVar

from fastapi import FastAPI
from servicelib.async_utils import cancel_sequential_workers
from servicelib.fastapi import long_running_tasks
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.logging_utils import config_all_loggers
from simcore_sdk.node_ports_common.exceptions import NodeNotFound

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME, SUMMARY, __version__
from ..api.rest import get_main_router
from ..api.rpc.routes import setup_rpc_api_routes
from ..models.schemas.application_health import ApplicationHealth
from ..models.shared_store import SharedStore, setup_shared_store
from ..modules.attribute_monitor import setup_attribute_monitor
from ..modules.inputs import setup_inputs
from ..modules.mounted_fs import MountedVolumes, setup_mounted_fs
from ..modules.notifications import setup_notifications
from ..modules.outputs import setup_outputs
from ..modules.prometheus_metrics import setup_prometheus_metrics
from ..modules.resource_tracking import setup_resource_tracking
from ..modules.system_monitor import setup_system_monitor
from ..modules.user_services_preferences import setup_user_services_preferences
from .docker_compose_utils import docker_compose_down
from .docker_logs import setup_background_log_fetcher
from .error_handlers import http_error_handler, node_not_found_error_handler
from .errors import BaseDynamicSidecarError
from .external_dependencies import setup_check_dependencies
from .rabbitmq import setup_rabbitmq
from .reserved_space import setup as setup_reserved_space
from .settings import ApplicationSettings
from .utils import volumes_fix_permissions

_LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
_NOISY_LOGGERS = (
    "aio_pika",
    "aiormq",
    "httpcore",
)

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

    _STATES: ClassVar[dict[str, Any]] = {
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
            msg = f"These app states were not properly initialized: {errors}"
            raise ValueError(msg)

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
    config_all_loggers(
        log_format_local_dev_enabled=settings.DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.DY_SIDECAR_LOG_FILTER_MAPPING,
    )


def create_base_app() -> FastAPI:
    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + _LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)

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

    app.include_router(get_main_router(app))

    setup_reserved_space(app)

    return app


def create_app():
    """
    Creates the application from using the env vars as a context
    Also stores inside the state all instances of classes
    needed in other requests and used to share data.
    """

    app = create_base_app()

    # MODULES SETUP --------------

    setup_check_dependencies(app)

    setup_shared_store(app)
    app.state.application_health = ApplicationHealth()
    application_settings: ApplicationSettings = app.state.settings

    setup_rabbitmq(app)
    setup_rpc_api_routes(app)
    setup_background_log_fetcher(app)
    setup_resource_tracking(app)
    setup_notifications(app)
    setup_system_monitor(app)

    setup_mounted_fs(app)
    setup_inputs(app)
    setup_outputs(app)

    setup_attribute_monitor(app)

    setup_user_services_preferences(app)

    if application_settings.are_prometheus_metrics_enabled:
        setup_prometheus_metrics(app)

    # ERROR HANDLERS  ------------
    app.add_exception_handler(NodeNotFound, node_not_found_error_handler)
    app.add_exception_handler(BaseDynamicSidecarError, http_error_handler)

    # EVENTS ---------------------

    async def _on_startup() -> None:
        app.state.container_restart_lock = Lock()

        app_state = AppState(app)
        await volumes_fix_permissions(app_state.mounted_volumes)
        # STARTED
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

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
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
