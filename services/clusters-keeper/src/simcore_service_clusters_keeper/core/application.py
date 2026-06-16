import logging

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.health import HealthCheckError, health_check_error_handler
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
from servicelib.fastapi.monitoring import (
    configure_prometheus_instrumentation,
)
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
    APP_STARTED_DISABLED_BANNER_MSG,
    APP_STARTING_BANNER_MSG,
)
from ..api.routes import setup_api_routes
from ..modules.clusters_management_task import configure_clusters_management
from ..modules.ec2 import configure_ec2_client
from ..modules.rabbitmq import configure_rabbitmq_client
from ..modules.redis import configure_redis_client
from ..modules.ssm import configure_ssm_client
from ..rpc.rpc_routes import configure_rpc_routes
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> None:
    configure_redis_client(app_lifespan)
    configure_rabbitmq_client(app_lifespan)
    configure_ec2_client(app_lifespan)
    configure_ssm_client(app_lifespan)
    configure_rpc_routes(app_lifespan)
    configure_clusters_management(app_lifespan, settings=settings)

    if settings.CLUSTERS_KEEPER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        configure_prometheus_instrumentation(app, app_lifespan)

    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(
            app,
            app_lifespan,
            tracing_config=tracing_config,
        )


def create_app(
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    _logger.info("app settings: %s", settings.model_dump_json(indent=1))

    started_banner = APP_STARTED_BANNER_MSG
    if any(
        s is None
        for s in [
            settings.CLUSTERS_KEEPER_EC2_ACCESS,
            settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES,
        ]
    ):
        started_banner = f"{APP_STARTED_BANNER_MSG}\n{APP_STARTED_DISABLED_BANNER_MSG}"

    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=started_banner,
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
        app = FastAPI(
            debug=settings.CLUSTERS_KEEPER_DEBUG,
            title=APP_NAME,
            description="Service to keep external clusters alive",
            version=API_VERSION,
            openapi_url=f"/api/{API_VTAG}/openapi.json",
            docs_url="/dev/doc",
            redoc_url=None,  # default disabled
            lifespan=app_lifespan,
        )
        app.state.settings = settings
        app.state.tracing_config = tracing_config
        assert app.state.settings.API_VERSION == API_VERSION  # nosec

        setup_api_routes(app)
        _configure_plugins(app, app_lifespan, settings, tracing_config)

        app.add_exception_handler(HealthCheckError, health_check_error_handler)

    return app
