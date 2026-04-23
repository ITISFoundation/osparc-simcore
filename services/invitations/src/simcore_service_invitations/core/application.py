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
    APP_NAME,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.routes import setup_api_routes
from . import events, exceptions_handlers
from .settings import ApplicationSettings


def create_app(
    settings: ApplicationSettings | None = None,
    logging_lifespan: Lifespan | None = None,
    tracing_config: TracingConfig | None = None,
) -> FastAPI:
    settings = settings or ApplicationSettings.create_from_envs()
    tracing_config = tracing_config or TracingConfig.create(
        service_name=APP_NAME, tracing_settings=settings.INVITATIONS_TRACING
    )

    app = FastAPI(
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled, see below
        lifespan=events.create_app_lifespan(
            settings=settings, logging_lifespan=logging_lifespan
        ),
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
