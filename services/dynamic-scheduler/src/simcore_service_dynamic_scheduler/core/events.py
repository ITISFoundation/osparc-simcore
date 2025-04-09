from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.docker import (
    get_remote_docker_client_main_lifespan,
    lifespan_remote_docker_client,
)
from servicelib.fastapi.prometheus_instrumentation import (
    get_prometheus_instrumentationmain_main_lifespan,
    lifespan_prometheus_instrumentation,
)

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..api.rpc.routes import lifespan_rpc_api_routes
from ..services.catalog import lifespan_catalog
from ..services.deferred_manager import lifespan_deferred_manager
from ..services.director_v0 import lifespan_director_v0
from ..services.director_v2 import lifespan_director_v2
from ..services.notifier import get_lifespans_notifier
from ..services.rabbitmq import lifespan_rabbitmq
from ..services.redis import lifespan_redis
from ..services.service_tracker import lifespan_service_tracker
from ..services.status_monitor import lifespan_status_monitor
from .settings import ApplicationSettings


async def _banner_lifespan(app: FastAPI) -> AsyncIterator[State]:
    _ = app
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


async def _main_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings

    yield {
        **get_prometheus_instrumentationmain_main_lifespan(
            enabled=settings.DYNAMIC_SCHEDULER_PROMETHEUS_INSTRUMENTATION_ENABLED
        ),
        **get_remote_docker_client_main_lifespan(
            settings.DYNAMIC_SCHEDULER_DOCKER_API_PROXY
        ),
    }


def create_app_lifespan() -> LifespanManager:
    app_lifespan = LifespanManager()
    app_lifespan.add(_main_lifespan)

    app_lifespan.add(lifespan_director_v2)
    app_lifespan.add(lifespan_director_v0)
    app_lifespan.add(lifespan_catalog)
    app_lifespan.add(lifespan_rabbitmq)
    app_lifespan.add(lifespan_rpc_api_routes)
    app_lifespan.add(lifespan_redis)

    for lifespan in get_lifespans_notifier():
        app_lifespan.add(lifespan)

    app_lifespan.add(lifespan_service_tracker)
    app_lifespan.add(lifespan_deferred_manager)
    app_lifespan.add(lifespan_status_monitor)

    app_lifespan.add(lifespan_remote_docker_client)

    app_lifespan.add(lifespan_prometheus_instrumentation)

    app_lifespan.add(_banner_lifespan)

    return app_lifespan
