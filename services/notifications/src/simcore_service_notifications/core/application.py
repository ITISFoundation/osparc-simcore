import logging

from fastapi import FastAPI
from servicelib.fastapi.monitoring import (
    initialize_prometheus_instrumentation,
)
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.fastapi.tracing import (
    setup_fastapi_app_tracing,
    setup_tracing,
)
from servicelib.logging_utils import config_all_loggers

from .._meta import API_VTAG, APP_NAME, SUMMARY, VERSION
from ..api.rest.routing import initialize_rest_api
from . import events
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


def create_app() -> FastAPI:
    settings = ApplicationSettings.create_from_envs()
    _logger.debug(settings.model_dump_json(indent=2))

    _initialise_logger(settings)

    assert settings.SC_BOOT_MODE  # nosec
    app = FastAPI(
        debug=settings.SC_BOOT_MODE.is_devel_mode(),
        title=APP_NAME,
        description=SUMMARY,
        version=f"{VERSION}",
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        lifespan=events.create_app_lifespan(),
        **get_common_oas_options(is_devel_mode=settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = settings

    if settings.NOTIFICATIONS_TRACING:
        setup_tracing(app, settings.NOTIFICATIONS_TRACING, APP_NAME)  # pragma: no cover

    initialize_rest_api(app)

    if settings.NOTIFICATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED:
        initialize_prometheus_instrumentation(app)

    if settings.NOTIFICATIONS_TRACING:
        setup_fastapi_app_tracing(app)

    return app
