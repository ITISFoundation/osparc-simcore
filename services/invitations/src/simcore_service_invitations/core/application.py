import logging

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from servicelib.fastapi.lifespan_utils import Lifespan
from servicelib.fastapi.monitoring import (
    initialize_prometheus_instrumentation,
)
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import (
    initialize_fastapi_app_tracing,
    setup_tracing,
)
from servicelib.tracing import TracingConfig

from .._meta import (
    API_VERSION,
    API_VTAG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.routes import setup_api_routes
from . import events, exceptions_handlers
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def create_app(
    tracing_config: TracingConfig,
    settings: ApplicationSettings | None = None,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    if not settings:
        settings = ApplicationSettings.create_from_envs()
        _logger.info(
            "Application settings: %s",
            json_dumps(settings, indent=2, sort_keys=True),
        )

    app = FastAPI(
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled, see below
        lifespan=events.create_app_lifespan(settings=settings, logging_lifespan=logging_lifespan),
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings
    app.state.tracing_config = tracing_config
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    if tracing_config.tracing_enabled:
        setup_tracing(app, tracing_config=tracing_config)

    # PLUGINS SETUP
    setup_api_routes(app)

    if settings.INVITATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED:
        initialize_prometheus_instrumentation(app)

    if tracing_config.tracing_enabled:
        initialize_fastapi_app_tracing(app, tracing_config=tracing_config)

    # ERROR HANDLERS
    exceptions_handlers.setup(app)

    return app
