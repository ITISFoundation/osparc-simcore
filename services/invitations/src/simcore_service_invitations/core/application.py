from fastapi import FastAPI
from servicelib.fastapi.monitoring import (
    setup_prometheus_instrumentation,
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
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.routes import setup_api_routes
from . import exceptions_handlers
from .settings import ApplicationSettings


def create_app(
    settings: ApplicationSettings | None = None,
    tracing_config: TracingConfig | None = None,
) -> FastAPI:
    app = FastAPI(
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled, see below
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings or ApplicationSettings()  # type: ignore[call-arg]
    tracing_config = tracing_config or TracingConfig.create(
        service_name=APP_NAME, tracing_settings=app.state.settings.INVITATIONS_TRACING
    )
    app.state.tracing_config = tracing_config
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    if tracing_config.tracing_enabled:
        setup_tracing(app, tracing_config=tracing_config)

    # PLUGINS SETUP
    setup_api_routes(app)

    if app.state.settings.INVITATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    if tracing_config.tracing_enabled:
        initialize_fastapi_app_tracing(app, tracing_config=tracing_config)

    # ERROR HANDLERS
    exceptions_handlers.setup(app)

    # EVENTS
    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
