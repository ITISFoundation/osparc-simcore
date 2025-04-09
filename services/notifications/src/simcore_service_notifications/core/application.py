import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.fastapi.lifespan_utils import LifespanGenerator, combine_lifespans
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.fastapi.tracing import initialize_tracing
from servicelib.logging_utils import config_all_loggers

from .._meta import (
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    SUMMARY,
    VERSION,
)
from ..api.rest.routing import initialize_rest_api
from ..api.rpc.routing import lifespan_rpc_api_routes
from ..services.postgres.service import lifespan_postgres
from ..services.rabbitmq import lifespan_rabbitmq
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _initialise_logger(settings: ApplicationSettings):
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
    logging.basicConfig(level=settings.LOG_LEVEL.value)  # NOSONAR
    logging.root.setLevel(settings.LOG_LEVEL.value)
    config_all_loggers(
        log_format_local_dev_enabled=settings.NOTIFICATIONS_VOLUMES_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.NOTIFICATIONS_VOLUMES_LOG_FILTER_MAPPING,
        tracing_settings=settings.NOTIFICATIONS_TRACING,
    )


async def _lifespan_banner(app: FastAPI) -> AsyncIterator[State]:
    _ = app
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


def create_app() -> FastAPI:
    settings = ApplicationSettings.create_from_envs()
    _logger.debug(settings.model_dump_json(indent=2))

    _initialise_logger(settings)

    lifespans: list[LifespanGenerator] = [
        lifespan_rabbitmq,
        lifespan_postgres,
        lifespan_rpc_api_routes,
    ]

    assert settings.SC_BOOT_MODE  # nosec
    app = FastAPI(
        debug=settings.SC_BOOT_MODE.is_devel_mode(),
        title=APP_NAME,
        description=SUMMARY,
        version=f"{VERSION}",
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        lifespan=combine_lifespans(*lifespans, _lifespan_banner),
        **get_common_oas_options(is_devel_mode=settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = settings

    initialize_rest_api(app)

    if settings.NOTIFICATIONS_TRACING:
        initialize_tracing(app, settings.NOTIFICATIONS_TRACING, APP_NAME)

    return app
