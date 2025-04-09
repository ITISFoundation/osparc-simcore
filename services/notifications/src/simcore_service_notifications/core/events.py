from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.postgres_lifespan import (
    PostgresLifespanState,
    postgres_database_lifespan,
)
from servicelib.fastapi.prometheus_instrumentation import (
    lifespan_prometheus_instrumentation,
)

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..api.rpc.routing import rpc_api_routes_lifespan
from ..services.postgres import postgres_lifespan
from ..services.rabbitmq import rabbitmq_lifespan
from .settings import ApplicationSettings


async def _banner_lifespan(app: FastAPI) -> AsyncIterator[State]:
    _ = app
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


async def _main_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    yield {
        PostgresLifespanState.POSTGRES_SETTINGS: settings.NOTIFICATIONS_POSTGRES,
        "prometheus_instrumentation_enabled": settings.NOTIFICATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED,
    }


async def _prometheus_instrumentation_lifespan(  # TODO: put this into one single setup like we did for the DB
    app: FastAPI, state: State
) -> AsyncIterator[State]:
    if state.get("prometheus_instrumentation_enabled", False):
        async for prometheus_state in lifespan_prometheus_instrumentation(app):
            yield prometheus_state


def create_app_lifespan():
    # WARNING: order matters
    app_lifespan = LifespanManager()
    app_lifespan.add(_main_lifespan)

    # - postgres
    app_lifespan.add(postgres_database_lifespan)
    app_lifespan.add(postgres_lifespan)

    # - rabbitmq
    app_lifespan.add(rabbitmq_lifespan)

    # - rpc api routes
    app_lifespan.add(rpc_api_routes_lifespan)

    # - prometheus instrumentation
    app_lifespan.add(_prometheus_instrumentation_lifespan)

    app_lifespan.add(_banner_lifespan)

    return app_lifespan
