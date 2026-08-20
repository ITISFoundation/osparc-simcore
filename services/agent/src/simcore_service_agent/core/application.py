import logging

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.fastapi.tracing import (
    configure_fastapi_app_tracing,
    get_tracing_config,
)
from servicelib.tracing import TracingConfig

from .._meta import (
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    APP_STARTING_BANNER_MSG,
    SUMMARY,
    VERSION,
)
from ..api.rest.routes import setup_rest_api
from ..api.rpc.routes import configure_rpc_api_routes
from ..services.containers_manager import configure_containers_manager
from ..services.instrumentation import configure_instrumentation
from ..services.rabbitmq import configure_rabbitmq
from ..services.volumes_manager import configure_volume_manager
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> None:
    if settings.AGENT_PROMETHEUS_INSTRUMENTATION_ENABLED:
        configure_instrumentation(app, app_lifespan)

    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(
            app,
            app_lifespan,
            tracing_config=tracing_config,
        )

    configure_rabbitmq(app_lifespan)
    configure_volume_manager(app_lifespan)
    configure_containers_manager(app_lifespan)
    configure_rpc_api_routes(app_lifespan)


def create_app(
    settings: ApplicationSettings | None = None,
    tracing_config: TracingConfig | None = None,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    if settings is None:
        settings = ApplicationSettings.create_from_envs()
        _logger.info(
            "Application settings: %s",
            json_dumps(settings, indent=2, sort_keys=True),
        )
    if tracing_config is None:
        tracing_config = TracingConfig.create(service_name=APP_NAME, tracing_settings=settings.AGENT_TRACING)

    assert settings.SC_BOOT_MODE  # nosec
    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=APP_STARTED_BANNER_MSG,
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
        app = FastAPI(
            debug=settings.SC_BOOT_MODE.is_devel_mode(),
            title=APP_NAME,
            description=SUMMARY,
            version=f"{VERSION}",
            openapi_url=f"/api/{API_VTAG}/openapi.json",
            lifespan=app_lifespan,
            **get_common_oas_options(is_devel_mode=settings.SC_BOOT_MODE.is_devel_mode()),
        )
        override_fastapi_openapi_method(app)
        app.state.settings = settings
        app.state.tracing_config = tracing_config

        _configure_plugins(app, app_lifespan, settings, get_tracing_config(app))

    setup_rest_api(app)

    return app
