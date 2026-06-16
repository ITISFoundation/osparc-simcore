from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.docker import (
    configure_remote_docker_client,
)
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
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
    APP_STARTING_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.frontend import configure_frontend
from ..api.rest.routes import configure_rest_api
from ..api.rpc.routes import configure_rpc_api
from ..services.catalog import configure_catalog
from ..services.deferred_manager import configure_deferred_manager
from ..services.director_v0 import configure_director_v0
from ..services.director_v2 import configure_director_v2
from ..services.fire_and_forget import configure_fire_and_forget
from ..services.notifier import configure_notifier
from ..services.rabbitmq import configure_rabbitmq_client
from ..services.redis import configure_redis_clients
from ..services.service_tracker import configure_service_tracker
from ..services.status_monitor import configure_status_monitor
from .settings import ApplicationSettings


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> None:
    configure_postgres_database(
        app_lifespan,
        settings=settings.DYNAMIC_SCHEDULER_POSTGRES,
    )
    configure_remote_docker_client(
        app_lifespan,
        settings=settings.DYNAMIC_SCHEDULER_DOCKER_API_PROXY,
    )

    configure_fire_and_forget(app_lifespan)
    configure_director_v2(app_lifespan)
    configure_director_v0(app_lifespan)
    configure_catalog(app_lifespan)
    configure_rabbitmq_client(app_lifespan)
    configure_rpc_api(app_lifespan)
    configure_redis_clients(app_lifespan, settings=settings.DYNAMIC_SCHEDULER_REDIS)
    configure_notifier(app_lifespan)
    configure_service_tracker(app_lifespan)
    configure_deferred_manager(app_lifespan)
    configure_status_monitor(app_lifespan)

    if settings.DYNAMIC_SCHEDULER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        configure_prometheus_instrumentation(app, app_lifespan)

    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(
            app,
            app_lifespan,
            tracing_config=tracing_config,
        )


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

    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=APP_STARTED_BANNER_MSG,
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
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

        _configure_plugins(app, app_lifespan, app_settings, app_tracing_config)

    return app
