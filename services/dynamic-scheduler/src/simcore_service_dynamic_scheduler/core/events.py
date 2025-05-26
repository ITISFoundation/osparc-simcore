from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.docker import (
    create_remote_docker_client_input_state,
    remote_docker_client_lifespan,
)
from servicelib.fastapi.monitoring import (
    create_prometheus_instrumentationmain_input_state,
    prometheus_instrumentation_lifespan,
)
from servicelib.fastapi.postgres_lifespan import (
    create_postgres_database_input_state,
)
from servicelib.fastapi.tracing import get_tracing_instrumentation_lifespan

from .._meta import APP_FINISHED_BANNER_MSG, APP_NAME, APP_STARTED_BANNER_MSG
from ..api.rpc.routes import rpc_api_routes_lifespan
from ..repository.events import repository_lifespan_manager
from ..services.catalog import catalog_lifespan
from ..services.deferred_manager import deferred_manager_lifespan
from ..services.director_v0 import director_v0_lifespan
from ..services.director_v2 import director_v2_lifespan
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


async def _settings_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings

    yield {
        **create_postgres_database_input_state(settings.DYNAMIC_SCHEDULER_POSTGRES),
        **create_prometheus_instrumentationmain_input_state(
            enabled=settings.DYNAMIC_SCHEDULER_PROMETHEUS_INSTRUMENTATION_ENABLED
        ),
        **create_remote_docker_client_input_state(
            settings.DYNAMIC_SCHEDULER_DOCKER_API_PROXY
        ),
    }


def create_app_lifespan(settings: ApplicationSettings) -> LifespanManager:
    app_lifespan = LifespanManager()
    app_lifespan.add(_settings_lifespan)

    if settings.DYNAMIC_SCHEDULER_TRACING:
        app_lifespan.add(
            get_tracing_instrumentation_lifespan(
                tracing_settings=settings.DYNAMIC_SCHEDULER_TRACING,
                service_name=APP_NAME,
            )
        )

    app_lifespan.include(repository_lifespan_manager)
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

    app_lifespan.add(remote_docker_client_lifespan)

    app_lifespan.add(prometheus_instrumentation_lifespan)

    app_lifespan.add(_banner_lifespan)

    return app_lifespan
