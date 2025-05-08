from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.postgres_lifespan import (
    create_postgres_database_input_state,
    postgres_database_lifespan,
)
from servicelib.fastapi.prometheus_instrumentation import (
    create_prometheus_instrumentationmain_input_state,
    prometheus_instrumentation_lifespan,
)

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..api.rpc.routing import rpc_api_routes_lifespan
from ..clients.postgres import postgres_lifespan
from ..clients.rabbitmq import rabbitmq_lifespan
from .settings import ApplicationSettings


async def _banner_lifespan(app: FastAPI) -> AsyncIterator[State]:
    _ = app
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


async def _settings_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    yield {
        **create_postgres_database_input_state(settings.NOTIFICATIONS_POSTGRES),
        **create_prometheus_instrumentationmain_input_state(
            enabled=settings.NOTIFICATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED
        ),
    }


def create_app_lifespan():
    # WARNING: order matters
    app_lifespan = LifespanManager()
    app_lifespan.add(_settings_lifespan)

    # - postgres
    app_lifespan.add(postgres_database_lifespan)
    app_lifespan.add(postgres_lifespan)

    # - rabbitmq
    app_lifespan.add(rabbitmq_lifespan)

    # - rpc api routes
    app_lifespan.add(rpc_api_routes_lifespan)

    # - prometheus instrumentation
    app_lifespan.add(prometheus_instrumentation_lifespan)

    app_lifespan.add(_banner_lifespan)

    return app_lifespan
