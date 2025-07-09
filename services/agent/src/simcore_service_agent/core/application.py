import logging

from fastapi import FastAPI
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.fastapi.tracing import (
    initialize_fastapi_app_tracing,
    setup_tracing,
)
from servicelib.logging_utils import setup_loggers

from .._meta import (
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    SUMMARY,
    VERSION,
)
from ..api.rest.routes import setup_rest_api
from ..api.rpc.routes import setup_rpc_api_routes
from ..services.containers_manager import setup_containers_manager
from ..services.instrumentation import setup_instrumentation
from ..services.rabbitmq import setup_rabbitmq
from ..services.volumes_manager import setup_volume_manager
from .settings import ApplicationSettings

logger = logging.getLogger(__name__)


def _setup_logger(settings: ApplicationSettings):
    setup_loggers(
        log_format_local_dev_enabled=settings.AGENT_VOLUMES_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.AGENT_VOLUMES_LOG_FILTER_MAPPING,
        tracing_settings=settings.AGENT_TRACING,
        log_base_level=settings.log_level,
        noisy_loggers=(),
    )


def create_app() -> FastAPI:
    settings = ApplicationSettings.create_from_envs()
    _setup_logger(settings)
    logger.debug(settings.model_dump_json(indent=2))

    assert settings.SC_BOOT_MODE  # nosec
    app = FastAPI(
        debug=settings.SC_BOOT_MODE.is_devel_mode(),
        title=APP_NAME,
        description=SUMMARY,
        version=f"{VERSION}",
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        **get_common_oas_options(is_devel_mode=settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = settings

    if settings.AGENT_TRACING:
        setup_tracing(app, settings.AGENT_TRACING, APP_NAME)

    setup_instrumentation(app)

    setup_rabbitmq(app)
    setup_volume_manager(app)
    setup_containers_manager(app)
    setup_rest_api(app)
    setup_rpc_api_routes(app)

    if settings.AGENT_TRACING:
        initialize_fastapi_app_tracing(app)

    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
