import logging

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
from servicelib.fastapi.monitoring import (
    configure_prometheus_instrumentation,
)
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.fastapi.postgres_lifespan import configure_postgres_database
from servicelib.fastapi.tracing import configure_fastapi_app_tracing
from servicelib.tracing import TracingConfig

from .._meta import (
    API_VTAG,
    APP_NAME,
    APP_SHUTDOWN_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
    APP_STARTING_BANNER_MSG,
    APP_WORKER_STARTED_BANNER_MSG,
    SUMMARY,
    VERSION,
)
from ..api.rest.routes import configure_rest_api
from ..api.rpc.routes import configure_rpc_api
from ..clients.celery import configure_task_manager
from ..clients.postgres import configure_postgres_liveness
from ..clients.rabbitmq import configure_rabbitmq_client
from ..clients.redis import configure_redis_client
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> None:
    configure_postgres_database(
        app_lifespan,
        settings=settings.NOTIFICATIONS_POSTGRES,
    )
    configure_postgres_liveness(app_lifespan)

    if not settings.NOTIFICATIONS_WORKER_MODE:
        configure_rabbitmq_client(app_lifespan)
        configure_rpc_api(app_lifespan)

    configure_redis_client(app_lifespan)
    configure_task_manager(app_lifespan)

    if settings.NOTIFICATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED:
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
    settings = settings or ApplicationSettings.create_from_envs()
    tracing_config = tracing_config or TracingConfig.create(
        service_name=APP_NAME, tracing_settings=settings.NOTIFICATIONS_TRACING
    )

    started_banner = APP_WORKER_STARTED_BANNER_MSG if settings.NOTIFICATIONS_WORKER_MODE else APP_STARTED_BANNER_MSG

    assert settings.SC_BOOT_MODE  # nosec
    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=started_banner,
        shutdown_complete_banner=APP_SHUTDOWN_BANNER_MSG,
    ) as app_lifespan:
        app = FastAPI(
            debug=settings.SC_BOOT_MODE.is_devel_mode(),
            title=APP_NAME,
            description=SUMMARY,
            version=f"{VERSION}",
            openapi_url=f"/api/{API_VTAG}/openapi.json",
            lifespan=app_lifespan,
            **get_common_oas_options(is_devel_mode=settings.SC_BOOT_MODE.is_devel_mode()),
        )
        override_fastapi_openapi_method(app)
        app.state.settings = settings
        app.state.tracing_config = tracing_config

        _configure_plugins(app, app_lifespan, settings, tracing_config)

    configure_rest_api(app)

    return app
