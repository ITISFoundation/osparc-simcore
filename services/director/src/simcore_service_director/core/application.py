import logging

from fastapi import FastAPI
from servicelib.fastapi.cancellation_middleware import RequestCancellationMiddleware
from servicelib.fastapi.http_error import set_app_default_http_error_handlers
from servicelib.fastapi.lifespan_utils import Lifespan
from servicelib.fastapi.monitoring import initialize_prometheus_instrumentation
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import (
    initialize_fastapi_app_tracing,
)
from servicelib.tracing import TracingConfig

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_NAME,
)
from ..api.rest.routes import setup_api_routes
from ..modules.redis import setup as setup_redis
from . import events
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def create_app(
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
    logging_lifespan: Lifespan | None,
) -> FastAPI:
    app = FastAPI(
        debug=settings.DIRECTOR_DEBUG,
        title=APP_NAME,
        description="Director-v0 service",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
        lifespan=events.create_app_lifespan(
            logging_lifespan=logging_lifespan,
            tracing_config=tracing_config,
        ),
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings
    app.state.tracing_config = tracing_config

    # PLUGINS SETUP
    setup_api_routes(app)

    if settings.DIRECTOR_REGISTRY_CACHING:
        setup_redis(app)

    app.add_middleware(RequestCancellationMiddleware)

    if settings.DIRECTOR_MONITORING_ENABLED:
        initialize_prometheus_instrumentation(app)

    if tracing_config.tracing_enabled:
        initialize_fastapi_app_tracing(app, tracing_config=tracing_config)

    # ERROR HANDLERS
    set_app_default_http_error_handlers(app)

    return app
