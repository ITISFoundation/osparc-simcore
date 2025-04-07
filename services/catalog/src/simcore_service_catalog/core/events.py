import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.postgres_lifespan import (
    PostgresLifespanStateKeys,
    postgres_lifespan,
)
from servicelib.fastapi.prometheus_instrumentation import (
    lifespan_prometheus_instrumentation,
)
from servicelib.fastapi.tracing import initialize_tracing

from .._meta import APP_FINISHED_BANNER_MSG, APP_NAME, APP_STARTED_BANNER_MSG
from ..api.rpc.routes import setup_rpc_api_routes
from ..db.events import setup_database
from ..services.director import setup_director
from ..services.function_services import setup_function_services
from ..services.rabbitmq import setup_rabbitmq
from .background_tasks import setup_background_task
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

    if settings.CATALOG_TRACING:
        initialize_tracing(app, settings.CATALOG_TRACING, APP_NAME)

    yield {
        PostgresLifespanStateKeys.POSTGRES_SETTINGS: settings.CATALOG_POSTGRES,
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
    postgres_lifespan.add(setup_database)
    app_lifespan.include(postgres_lifespan)

    # - rabbitmq lifespan
    app_lifespan.add(setup_rabbitmq)

    # - rpc api routes lifespan
    app_lifespan.add(setup_rpc_api_routes)

    # - director lifespan
    app_lifespan.add(setup_director)

    # - function services lifespan
    app_lifespan.add(setup_function_services)

    # - background task lifespan
    app_lifespan.add(setup_background_task)

    # - prometheus instrumentation lifespan
    app_lifespan.add(_setup_prometheus_instrumentation_adapter)

    return app_lifespan
