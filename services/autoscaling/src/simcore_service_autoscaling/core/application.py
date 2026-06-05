import logging
from collections.abc import AsyncIterator

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.health import HealthCheckError, health_check_error_handler
from servicelib.fastapi.lifespan_utils import Lifespan
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


async def _banners_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    if settings.AUTOSCALING_NODES_MONITORING:
        print(APP_STARTED_DYNAMIC_BANNER_MSG, flush=True)  # noqa: T201
    elif settings.AUTOSCALING_DASK:
        print(APP_STARTED_COMPUTATIONAL_BANNER_MSG, flush=True)  # noqa: T201
    else:
        print(APP_STARTED_DISABLED_BANNER_MSG, flush=True)  # noqa: T201
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

    if settings.AUTOSCALING_PROMETHEUS_INSTRUMENTATION_ENABLED:
        configure_prometheus_instrumentation(app, app_lifespan)
        configure_autoscaling_instrumentation(app_lifespan)

    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(app, app_lifespan, tracing_config=tracing_config)

    configure_docker_client(app_lifespan)
    if settings.AUTOSCALING_RABBITMQ is not None:
        configure_rabbitmq_client(app_lifespan)
    if settings.AUTOSCALING_EC2_ACCESS is not None:
        configure_ec2_client(app_lifespan)
    if settings.AUTOSCALING_SSM_ACCESS is not None:
        configure_ssm_client(app_lifespan)
    configure_redis_client(app_lifespan)

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

    app_lifespan.add(_banners_lifespan)


def create_app(
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    app_lifespan = LifespanManager()

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
    _logger.info(
        "Application settings: %s",
        json_dumps(settings, indent=2, sort_keys=True),
    )

    setup_api_routes(app)

    # ERROR HANDLERS
    app.add_exception_handler(HealthCheckError, health_check_error_handler)

    _configure_plugins(app, app_lifespan, settings, tracing_config, logging_lifespan)

    return app
