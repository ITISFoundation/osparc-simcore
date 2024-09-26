import logging

from fastapi import FastAPI
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from servicelib.logging_utils import config_all_loggers

from .._meta import (
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    SUMMARY,
    VERSION,
)
from ..services.rabbitmq import setup_rabbitmq
from ..services.service_volume_manager import setup_service_volume_manager
from .api.rest.routes import setup_rest_api
from .api.rpc.routes import setup_rpc_api_routes
from .settings import ApplicationSettings

logger = logging.getLogger(__name__)


def _setup_logger(settings: ApplicationSettings):
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
    logging.basicConfig(level=settings.LOGLEVEL.value)  # NOSONAR
    logging.root.setLevel(settings.LOGLEVEL.value)
    config_all_loggers(
        log_format_local_dev_enabled=settings.AGENT_VOLUMES_LOG_FORMAT_LOCAL_DEV_ENABLED
    )


def create_app() -> FastAPI:
    settings = ApplicationSettings.create_from_envs()
    _setup_logger(settings)
    logger.debug(settings.json(indent=2))

    assert settings.SC_BOOT_MODE  # nosec
    app = FastAPI(
        debug=settings.SC_BOOT_MODE.is_devel_mode(),
        title=APP_NAME,
        description=SUMMARY,
        version=f"{VERSION}",
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        **get_common_oas_options(settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = settings

    if app.state.settings.AGENT_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    setup_rabbitmq(app)
    setup_service_volume_manager(app)
    setup_rest_api(app)
    setup_rpc_api_routes(app)

    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
