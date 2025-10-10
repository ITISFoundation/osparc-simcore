import logging

from fastapi import FastAPI
from servicelib.async_utils import cancel_sequential_workers
from servicelib.fastapi.client_session import setup_client_session
from servicelib.fastapi.http_error import set_app_default_http_error_handlers
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
)
from ..api.rest.routes import setup_api_routes
from ..instrumentation import setup as setup_instrumentation
from ..registry_proxy import setup as setup_registry
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings, tracing_config: TracingConfig) -> FastAPI:
    app = FastAPI(
        debug=settings.DIRECTOR_DEBUG,
        title=APP_NAME,
        description="Director-v0 service",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )
    # STATE
    app.state.settings = settings
    app.state.tracing_config = tracing_config
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    # PLUGINS SETUP
    if tracing_config.tracing_enabled:
        setup_tracing(app, tracing_config)

    setup_api_routes(app)

    setup_instrumentation(app)

    setup_client_session(
        app,
        max_keepalive_connections=settings.DIRECTOR_REGISTRY_CLIENT_MAX_KEEPALIVE_CONNECTIONS,
        default_timeout=settings.DIRECTOR_REGISTRY_CLIENT_TIMEOUT,
        tracing_config=tracing_config,
    )
    setup_registry(app)

    if tracing_config.tracing_enabled:
        initialize_fastapi_app_tracing(app, tracing_config=tracing_config)

    # ERROR HANDLERS
    set_app_default_http_error_handlers(app)

    # EVENTS
    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    async def _on_shutdown() -> None:
        await cancel_sequential_workers()
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
