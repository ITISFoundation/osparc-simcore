from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.docker_utils import get_lifespan_remote_docker_client
from servicelib.fastapi.lifespan_utils import LifespanGenerator, combine_lifespans
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.profiler import initialize_profiler
from servicelib.fastapi.prometheus_instrumentation import (
    initialize_prometheus_instrumentation,
    lifespan_prometheus_instrumentation,
)
from servicelib.fastapi.tracing import get_lifespan_tracing

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.frontend import initialize_frontend
from ..api.rest.routes import initialize_rest_api
from ..api.rpc.routes import lifespan_rpc_api_routes
from ..services.deferred_manager import lifespan_deferred_manager
from ..services.director_v0 import lifespan_director_v0
from ..services.director_v2 import lifespan_director_v2
from ..services.notifier import get_notifier_lifespans
from ..services.rabbitmq import lifespan_rabbitmq
from ..services.redis import lifespan_redis
from ..services.service_tracker import lifespan_service_tracker
from ..services.status_monitor import lifespan_status_monitor
from .settings import ApplicationSettings


async def _lifespan_banner(app: FastAPI) -> AsyncIterator[State]:
    _ = app
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


def create_app(settings: ApplicationSettings | None = None) -> FastAPI:
    app_settings = settings or ApplicationSettings.create_from_envs()

    lifespans: list[LifespanGenerator] = [
        lifespan_director_v2,
        lifespan_director_v0,
        lifespan_rabbitmq,
        lifespan_rpc_api_routes,
        lifespan_redis,
        *get_notifier_lifespans(),
        lifespan_service_tracker,
        lifespan_deferred_manager,
        lifespan_status_monitor,
        get_lifespan_remote_docker_client("DYNAMIC_SCHEDULER_DOCKER_API_PROXY"),
    ]

    if app_settings.DYNAMIC_SCHEDULER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        lifespans.append(lifespan_prometheus_instrumentation)

    if app_settings.DYNAMIC_SCHEDULER_TRACING:
        lifespans.append(
            get_lifespan_tracing(app_settings.DYNAMIC_SCHEDULER_TRACING, APP_NAME)
        )

    app = FastAPI(
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url=(
            "/doc" if app_settings.DYNAMIC_SCHEDULER_SWAGGER_API_DOC_ENABLED else None
        ),
        redoc_url=None,
        lifespan=combine_lifespans(*lifespans, _lifespan_banner),
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = app_settings
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    initialize_rest_api(app)

    initialize_prometheus_instrumentation(app)

    initialize_frontend(app)

    if app_settings.DYNAMIC_SCHEDULER_PROFILING:
        initialize_profiler(app)

    return app
