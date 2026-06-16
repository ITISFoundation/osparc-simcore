import logging

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.health import HealthCheckError, health_check_error_handler
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
from servicelib.fastapi.monitoring import configure_prometheus_instrumentation
from servicelib.fastapi.tracing import configure_fastapi_app_tracing
from servicelib.tracing import TracingConfig

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    APP_STARTED_COMPUTATIONAL_BANNER_MSG,
    APP_STARTED_DISABLED_BANNER_MSG,
    APP_STARTED_DYNAMIC_BANNER_MSG,
    APP_STARTING_BANNER_MSG,
)
from ..api.routes import setup_api_routes
from ..modules.cluster_scaling.auto_scaling_task import configure_auto_scaling_task
from ..modules.cluster_scaling.warm_buffer_machines_pool_task import (
    configure_warm_buffer_machines_pool,
)
from ..modules.docker import configure_docker_client
from ..modules.ec2 import configure_ec2_client
from ..modules.instrumentation import configure_autoscaling_instrumentation
from ..modules.rabbitmq import configure_rabbitmq_client
from ..modules.redis import configure_redis_client
from ..modules.ssm import configure_ssm_client
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _get_started_banner(settings: ApplicationSettings) -> str:
    if settings.AUTOSCALING_NODES_MONITORING:
        mode_banner = APP_STARTED_DYNAMIC_BANNER_MSG
    elif settings.AUTOSCALING_DASK:
        mode_banner = APP_STARTED_COMPUTATIONAL_BANNER_MSG
    else:
        mode_banner = APP_STARTED_DISABLED_BANNER_MSG
    return f"{APP_STARTED_BANNER_MSG}\n{mode_banner}"


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager,
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> None:
    if settings.AUTOSCALING_PROMETHEUS_INSTRUMENTATION_ENABLED:
        configure_prometheus_instrumentation(app, app_lifespan)
        configure_autoscaling_instrumentation(app_lifespan)

    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(app, app_lifespan, tracing_config=tracing_config)

    configure_docker_client(app_lifespan)
    configure_rabbitmq_client(app_lifespan, settings=settings.AUTOSCALING_RABBITMQ)
    configure_ec2_client(app_lifespan)
    configure_ssm_client(app_lifespan)
    configure_redis_client(app_lifespan, settings=settings.AUTOSCALING_REDIS)

    if (
        settings.AUTOSCALING_EC2_ACCESS is not None
        and settings.AUTOSCALING_EC2_INSTANCES is not None
        and (settings.AUTOSCALING_NODES_MONITORING is not None or settings.AUTOSCALING_DASK is not None)
    ):
        configure_auto_scaling_task(app_lifespan)

    if (
        settings.AUTOSCALING_EC2_ACCESS is not None
        and settings.AUTOSCALING_EC2_INSTANCES is not None
        and settings.AUTOSCALING_SSM_ACCESS is not None
        and settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ATTACHED_IAM_PROFILE
        and settings.AUTOSCALING_NODES_MONITORING is not None
    ):
        configure_warm_buffer_machines_pool(app_lifespan)


def create_app(
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    _logger.info(
        "Application settings: %s",
        json_dumps(settings, indent=2, sort_keys=True),
    )

    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=_get_started_banner(settings),
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
        app = FastAPI(
            debug=settings.AUTOSCALING_DEBUG,
            title=APP_NAME,
            description="Service to auto-scale swarm",
            version=API_VERSION,
            openapi_url=f"/api/{API_VTAG}/openapi.json",
            docs_url="/dev/doc",
            redoc_url=None,  # default disabled
            lifespan=app_lifespan,
        )
        # STATE
        app.state.settings = settings
        app.state.tracing_config = tracing_config
        assert app.state.settings.API_VERSION == API_VERSION  # nosec

        _configure_plugins(app, app_lifespan, settings, tracing_config)

    setup_api_routes(app)

    # ERROR HANDLERS
    app.add_exception_handler(HealthCheckError, health_check_error_handler)

    return app
