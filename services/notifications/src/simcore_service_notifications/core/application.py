import logging

from fastapi import FastAPI
from servicelib.fastapi.lifespan_utils import Lifespan
from servicelib.fastapi.monitoring import (
    initialize_prometheus_instrumentation,
)
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.fastapi.tracing import (
    initialize_fastapi_app_tracing,
    setup_tracing,
)
from servicelib.tracing import TracingConfig

from .._meta import API_VTAG, APP_NAME, SUMMARY, VERSION
from ..api.rest.routing import initialize_rest_api
from . import events
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def create_app(
    settings: ApplicationSettings | None = None,
    logging_lifespan: Lifespan | None = None,
    tracing_config: TracingConfig | None = None,
) -> FastAPI:
    settings = settings or ApplicationSettings.create_from_envs()
    tracing_config = tracing_config or TracingConfig.create(
        service_name=APP_NAME, tracing_settings=settings.NOTIFICATIONS_TRACING
    )

    assert settings.SC_BOOT_MODE  # nosec
    app = FastAPI(
        debug=settings.SC_BOOT_MODE.is_devel_mode(),
        title=APP_NAME,
        description=SUMMARY,
        version=f"{VERSION}",
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        lifespan=events.create_app_lifespan(logging_lifespan=logging_lifespan),
        **get_common_oas_options(is_devel_mode=settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = settings
    app.state.tracing_config = tracing_config

    if tracing_config.tracing_enabled:
        setup_tracing(app, tracing_config=tracing_config)

    initialize_rest_api(app)

    if settings.NOTIFICATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED:
        initialize_prometheus_instrumentation(app)

    if tracing_config.tracing_enabled:
        initialize_fastapi_app_tracing(app, tracing_config=tracing_config)

    return app
