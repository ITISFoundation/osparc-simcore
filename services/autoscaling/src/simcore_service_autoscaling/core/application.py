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
from ..modules.cluster_scaling.auto_scaling_task import auto_scaling_task_lifespan
from ..modules.cluster_scaling.warm_buffer_machines_pool_task import (
    warm_buffer_machines_pool_lifespan,
)
from ..modules.docker import docker_lifespan
from ..modules.ec2 import ec2_lifespan
from ..modules.instrumentation import autoscaling_instrumentation_lifespan
from ..modules.rabbitmq import rabbitmq_lifespan
from ..modules.redis import redis_lifespan
from ..modules.ssm import ssm_lifespan
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
        configure_prometheus_instrumentation(app, app_lifespan, autoscaling_instrumentation_lifespan)

    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(app, app_lifespan, tracing_config=tracing_config)

    app_lifespan.add(docker_lifespan)
    app_lifespan.add(rabbitmq_lifespan)
    app_lifespan.add(ec2_lifespan)
    app_lifespan.add(ssm_lifespan)
    app_lifespan.add(redis_lifespan)
    app_lifespan.add(auto_scaling_task_lifespan)
    app_lifespan.add(warm_buffer_machines_pool_lifespan)

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
