from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.docker import (
    configure_remote_docker_client,
)
from servicelib.fastapi.lifespan_utils import Lifespan
from servicelib.fastapi.monitoring import (
    configure_prometheus_instrumentation,
)
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.postgres_lifespan import configure_postgres_database
from servicelib.fastapi.profiler import configure_profiler
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
    PROJECT_NAME,
    SUMMARY,
)
from ..api.frontend import configure_frontend
from ..api.rest.routes import configure_rest_api
from ..api.rpc.routes import rpc_api_routes_lifespan
from ..services.catalog import catalog_lifespan
from ..services.deferred_manager import deferred_manager_lifespan
from ..services.director_v0 import director_v0_lifespan
from ..services.director_v2 import director_v2_lifespan
from ..services.fire_and_forget import fire_and_forget_lifespan
from ..services.notifier import get_notifier_lifespans
from ..services.rabbitmq import rabbitmq_lifespan
from ..services.redis import redis_lifespan
from ..services.service_tracker import service_tracker_lifespan
from ..services.status_monitor import status_monitor_lifespan
from .settings import ApplicationSettings


async def _banner_lifespan(app: FastAPI) -> AsyncIterator[State]:
    _ = app
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager,
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
    logging_lifespan: Lifespan | None,
) -> None:
    if logging_lifespan:
        app_lifespan.add(logging_lifespan)

    configure_postgres_database(
        app_lifespan,
        settings=settings.DYNAMIC_SCHEDULER_POSTGRES,
    )
    configure_remote_docker_client(
        app_lifespan,
        settings=settings.DYNAMIC_SCHEDULER_DOCKER_API_PROXY,
    )

    app_lifespan.add(fire_and_forget_lifespan)
    app_lifespan.add(director_v2_lifespan)
    app_lifespan.add(director_v0_lifespan)
    app_lifespan.add(catalog_lifespan)
    app_lifespan.add(rabbitmq_lifespan)
    app_lifespan.add(rpc_api_routes_lifespan)
    app_lifespan.add(redis_lifespan)

    for lifespan in get_notifier_lifespans():
        app_lifespan.add(lifespan)

    app_lifespan.add(service_tracker_lifespan)
    app_lifespan.add(deferred_manager_lifespan)
    app_lifespan.add(status_monitor_lifespan)

    if settings.DYNAMIC_SCHEDULER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        configure_prometheus_instrumentation(app, app_lifespan)

    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(
            app,
            app_lifespan,
            tracing_config=tracing_config,
        )

    app_lifespan.add(_banner_lifespan)


def create_app(
    settings: ApplicationSettings | None = None,
    logging_lifespan: Lifespan | None = None,
    tracing_config: TracingConfig | None = None,
) -> FastAPI:
    app_settings = settings or ApplicationSettings.create_from_envs()
    app_tracing_config = tracing_config or TracingConfig.create(
        tracing_settings=app_settings.DYNAMIC_SCHEDULER_TRACING,
        service_name=APP_NAME,
    )

    app_lifespan = LifespanManager()

    app = FastAPI(
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url=("/doc" if app_settings.DYNAMIC_SCHEDULER_SWAGGER_API_DOC_ENABLED else None),
        redoc_url=None,
        lifespan=app_lifespan,
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = app_settings
    app.state.tracing_config = app_tracing_config
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    configure_rest_api(app)
    configure_frontend(app)

    if app_settings.DYNAMIC_SCHEDULER_PROFILING:
        configure_profiler(app)

    _configure_plugins(app, app_lifespan, app_settings, app_tracing_config, logging_lifespan)

    return app
