import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.cancellation_middleware import RequestCancellationMiddleware
from servicelib.fastapi.http_error import set_app_default_http_error_handlers
from servicelib.fastapi.httpx_client import configure_httpx_client
from servicelib.fastapi.lifespan_utils import Lifespan
from servicelib.fastapi.monitoring import configure_prometheus_instrumentation
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import (
    configure_fastapi_app_tracing,
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
from ..instrumentation import director_instrumentation_lifespan
from ..modules.docker_registry import configure_registry_lifespans
from ..modules.redis import redis_clients_manager_lifespan
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


async def _banners_lifespan(_: FastAPI) -> AsyncIterator[State]:
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


def create_app(
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
    logging_lifespan: Lifespan | None,
) -> FastAPI:
    app_lifespan = LifespanManager()
    if logging_lifespan:
        app_lifespan.add(logging_lifespan)

    app = FastAPI(
        debug=settings.DIRECTOR_DEBUG,
        title=APP_NAME,
        description="Director-v0 service",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
        lifespan=app_lifespan,
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings
    app.state.tracing_config = tracing_config

    # PLUGINS SETUP
    setup_api_routes(app)
    # Cancellation middleware
    app.add_middleware(RequestCancellationMiddleware)
    # ERROR HANDLERS
    set_app_default_http_error_handlers(app)

    configure_httpx_client(
        app_lifespan,
        max_keepalive_connections=settings.DIRECTOR_REGISTRY_CLIENT_MAX_KEEPALIVE_CONNECTIONS,
        default_timeout=settings.DIRECTOR_REGISTRY_CLIENT_TIMEOUT,
        tracing_config=tracing_config,
    )
    if settings.DIRECTOR_REGISTRY_CACHING:
        app_lifespan.add(redis_clients_manager_lifespan)
    configure_registry_lifespans(app_lifespan)

    configure_prometheus_instrumentation(
        app,
        app_lifespan,
        director_instrumentation_lifespan,
        enabled=settings.DIRECTOR_MONITORING_ENABLED,
    )

    configure_fastapi_app_tracing(
        app,
        app_lifespan,
        tracing_config=tracing_config,
    )

    # comes last to have the banner printed after all the setup is done
    app_lifespan.add(_banners_lifespan)

    return app
