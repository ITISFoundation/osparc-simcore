import logging
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
from ..api.rpc.routes import rpc_api_lifespan
from ..db.events import database_lifespan
from ..services.director import director_lifespan
from ..services.function_services import function_services_lifespan
from ..services.rabbitmq import rabbitmq_lifespan
from .background_tasks import background_task_lifespan
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def flush_started_banner() -> None:
    # WARNING: this function is spied in the tests
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201


def flush_finished_banner() -> None:
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


async def _setup_app(app: FastAPI) -> AsyncIterator[State]:
    flush_started_banner()

    settings: ApplicationSettings = app.state.settings

    yield {
        PostgresLifespanState.POSTGRES_SETTINGS: settings.CATALOG_POSTGRES,
        "prometheus_instrumentation_enabled": settings.CATALOG_PROMETHEUS_INSTRUMENTATION_ENABLED,
    }

    flush_finished_banner()


async def _setup_prometheus_instrumentation_adapter(
    app: FastAPI, state: State
) -> AsyncIterator[State]:
    enabled = state.get("prometheus_instrumentation_enabled", False)
    if enabled:
        async for prometheus_state in lifespan_prometheus_instrumentation(app):
            yield prometheus_state


def create_app_lifespan():
    # app lifespan
    app_lifespan = LifespanManager()
    app_lifespan.add(_setup_app)

    # WARNING: order matters

    # - postgres lifespan
    app_lifespan.add(postgres_database_lifespan)
    app_lifespan.add(database_lifespan)

    # - rabbitmq lifespan
    app_lifespan.add(rabbitmq_lifespan)

    # - rpc api routes lifespan
    app_lifespan.add(rpc_api_lifespan)

    # - director lifespan
    app_lifespan.add(director_lifespan)

    # - function services lifespan
    app_lifespan.add(function_services_lifespan)

    # - background task lifespan
    app_lifespan.add(background_task_lifespan)

    # - prometheus instrumentation lifespan
    app_lifespan.add(_setup_prometheus_instrumentation_adapter)

    return app_lifespan
