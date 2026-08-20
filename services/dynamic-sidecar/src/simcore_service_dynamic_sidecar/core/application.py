import logging
from asyncio import Lock
from collections.abc import AsyncIterator
from contextlib import AbstractContextManager
from typing import Any, ClassVar

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.lifespan_utils import configure_app_lifespan
from servicelib.fastapi.logging_lifespan import (
    create_logging_lifespan,
    create_logging_shutdown_event,
)
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.tracing import TracingConfig
from simcore_sdk.node_ports_common.exceptions import NodeNotFoundError

from .._meta import API_VERSION, API_VTAG, APP_NAME, SUMMARY, __version__
from ..models.schemas.application_health import ApplicationHealth
from ..models.shared_store import SharedStore
from ..modules.mounted_fs import MountedVolumes
from .docker_compose_utils import docker_compose_down
from .error_handlers import http_error_handler, node_not_found_error_handler
from .errors import BaseDynamicSidecarError
from .settings import ApplicationSettings
from .utils import volumes_fix_permissions

_NOISY_LOGGERS = ("httpcore",)

_logger = logging.getLogger(__name__)

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

""".format(f"v{__version__}")

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


def create_app_lifespan(
    app_settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> AbstractContextManager[LifespanManager[FastAPI]]:
    logging_lifespan = create_logging_lifespan(
        log_format_local_dev_enabled=app_settings.DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=app_settings.DY_SIDECAR_LOG_FILTER_MAPPING,
        tracing_config=tracing_config,
        log_base_level=app_settings.logging_level,
        noisy_loggers=_NOISY_LOGGERS,
    )
    return configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=f"Starting {APP_NAME}...",
        started_banner=APP_STARTED_BANNER_MSG,
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    )


def create_base_app(
    app_lifespan: LifespanManager[FastAPI] | None = None,
    *,
    app_settings: ApplicationSettings | None = None,
    tracing_config: TracingConfig | None = None,
) -> FastAPI:
    app_settings = app_settings or ApplicationSettings.create_from_envs()
    tracing_config = tracing_config or TracingConfig.create(
        service_name=APP_NAME,
        tracing_settings=app_settings.DYNAMIC_SIDECAR_TRACING,
    )

    _logger.info(
        "Application settings: %s",
        json_dumps(app_settings, indent=2, sort_keys=True),
    )

    # minimal
    assert app_settings.SC_BOOT_MODE  # nosec
    app = FastAPI(
        debug=app_settings.SC_BOOT_MODE.is_devel_mode(),
        title=APP_NAME,
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        **get_common_oas_options(is_devel_mode=app_settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = app_settings
    app.state.tracing_config = tracing_config

    # NOTE: lazy import for faster startup
    # ruff: noqa: PLC0415
    from ..api.rest import get_main_router
    from .reserved_space import setup as setup_reserved_space

    app.include_router(get_main_router(app))

    setup_reserved_space(app)

    if app_lifespan is None:
        app.add_event_handler(
            "shutdown",
            create_logging_shutdown_event(
                log_format_local_dev_enabled=app_settings.DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED,
                logger_filter_mapping=app_settings.DY_SIDECAR_LOG_FILTER_MAPPING,
                tracing_config=tracing_config,
                log_base_level=app_settings.logging_level,
                noisy_loggers=_NOISY_LOGGERS,
            ),
        )
    return app


def _configure_external_dependencies_and_shared_store(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI] | None,
) -> None:
    # NOTE: lazy imports for faster startup
    from ..models.shared_store import configure_shared_store, setup_shared_store
    from .external_dependencies import configure_check_dependencies, setup_check_dependencies

    if app_lifespan is None:
        setup_check_dependencies(app)
        setup_shared_store(app)
    else:
        configure_check_dependencies(app_lifespan)
        configure_shared_store(app_lifespan)


def _configure_rabbitmq_rpc_and_logs(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI] | None,
) -> None:
    # NOTE: lazy imports for faster startup
    from ..api.rpc.routes import configure_rpc_api_routes, setup_rpc_api_routes
    from .docker_logs import configure_background_log_fetcher, setup_background_log_fetcher
    from .rabbitmq import configure_rabbitmq, setup_rabbitmq

    if app_lifespan is None:
        setup_rabbitmq(app)
        setup_rpc_api_routes(app)
        setup_background_log_fetcher(app)
    else:
        configure_rabbitmq(app, app_lifespan)
        configure_rpc_api_routes(app_lifespan)
        configure_background_log_fetcher(app_lifespan)


# pylint: disable=too-many-statements
def create_app(  # noqa: PLR0915
    app_lifespan: LifespanManager[FastAPI] | None = None,
    *,
    app_settings: ApplicationSettings | None = None,
    tracing_config: TracingConfig | None = None,
) -> FastAPI:
    """
    Creates the application from using the env vars as a context
    Also stores inside the state all instances of classes
    needed in other requests and used to share data.
    """

    app = create_base_app(
        app_lifespan,
        app_settings=app_settings,
        tracing_config=tracing_config,
    )

    # MODULES SETUP --------------

    # NOTE: lazy import for faster startup
    # ruff: noqa: PLC0415
    from servicelib.fastapi.tracing import (
        configure_fastapi_app_tracing,
        get_tracing_config,
        initialize_fastapi_app_tracing,
        setup_tracing,
    )

    from ..modules.attribute_monitor import setup_attribute_monitor
    from ..modules.file_notification_subscriber import (
        setup_file_notification_subscriber,
    )
    from ..modules.inputs import setup_inputs
    from ..modules.long_running_tasks import setup_long_running_tasks
    from ..modules.mounted_fs import setup_mounted_fs
    from ..modules.notifications import setup_notifications
    from ..modules.outputs import setup_outputs
    from ..modules.prometheus_metrics import setup_prometheus_metrics
    from ..modules.r_clone_mount_manager import setup_r_clone_mount_manager
    from ..modules.resource_tracking import setup_resource_tracking
    from ..modules.system_monitor import setup_system_monitor
    from ..modules.user_services_preferences import setup_user_services_preferences

    _configure_external_dependencies_and_shared_store(app, app_lifespan)

    app.state.application_health = ApplicationHealth()
    application_settings: ApplicationSettings = app.state.settings

    tracing_config = get_tracing_config(app)

    if tracing_config.tracing_enabled:
        if app_lifespan is None:
            setup_tracing(app, tracing_config)
        else:
            configure_fastapi_app_tracing(
                app,
                app_lifespan,
                tracing_config=tracing_config,
            )

    _configure_rabbitmq_rpc_and_logs(app, app_lifespan)

    setup_resource_tracking(app)
    setup_notifications(app)

    setup_mounted_fs(app)
    setup_system_monitor(app)
    setup_inputs(app)
    setup_outputs(app)

    setup_long_running_tasks(app)

    setup_attribute_monitor(app)

    setup_user_services_preferences(app)

    setup_r_clone_mount_manager(app)

    setup_file_notification_subscriber(app)

    if application_settings.are_prometheus_metrics_enabled:
        setup_prometheus_metrics(app)

    if tracing_config.tracing_enabled and app_lifespan is None:
        initialize_fastapi_app_tracing(
            app,
            tracing_config=tracing_config,
        )

    # ERROR HANDLERS  ------------
    app.add_exception_handler(
        NodeNotFoundError,
        node_not_found_error_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(BaseDynamicSidecarError, http_error_handler)  # type: ignore[arg-type]

    # EVENTS ---------------------

    async def _application_lifespan() -> AsyncIterator[None]:
        app.state.container_restart_lock = Lock()

        try:
            app_state = AppState(app)
            await volumes_fix_permissions(app_state.mounted_volumes)
            yield
        finally:
            app_state = AppState(app)
            if docker_compose_yaml := app_state.compose_spec:
                _logger.info("Removing spawned containers")

                result = await docker_compose_down(docker_compose_yaml, app.state.settings)

                _logger.log(
                    logging.INFO if result.success else logging.ERROR,
                    "Removed spawned containers:\n%s",
                    result.message,
                )

    if app_lifespan is None:
        application_lifespan = _application_lifespan()

        async def _on_startup() -> None:
            await anext(application_lifespan)
            print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

        async def _on_shutdown() -> None:
            await application_lifespan.aclose()
            print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

        app.add_event_handler("startup", _on_startup)
        app.add_event_handler("shutdown", _on_shutdown)
    else:
        app_lifespan.add(_application_lifespan)

    return app
