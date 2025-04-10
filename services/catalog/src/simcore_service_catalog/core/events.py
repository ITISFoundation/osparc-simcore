import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.postgres_lifespan import (
    PostgresLifespanState,
)
from servicelib.fastapi.prometheus_instrumentation import (
    lifespan_prometheus_instrumentation,
)

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..api.rpc.events import rpc_api_lifespan
from ..clients.director import director_lifespan
from ..clients.rabbitmq import rabbitmq_lifespan
from ..repository.events import repository_lifespan_manager
from ..service.function_services import function_services_lifespan
from .background_tasks import background_task_lifespan
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _flush_started_banner() -> None:
    # WARNING: this function is spied in the tests
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201


def _flush_finished_banner() -> None:
    # WARNING: this function is spied in the tests
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


async def _banners_lifespan(_) -> AsyncIterator[State]:
    _flush_started_banner()
    yield {}
    _flush_finished_banner()


async def _main_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings

    yield {
        PostgresLifespanState.POSTGRES_SETTINGS: settings.CATALOG_POSTGRES,
        "prometheus_instrumentation_enabled": settings.CATALOG_PROMETHEUS_INSTRUMENTATION_ENABLED,
    }


async def _prometheus_instrumentation_lifespan(
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
    app_lifespan.include(repository_lifespan_manager)

    # - rabbitmq
    app_lifespan.add(rabbitmq_lifespan)

    # - rpc api routes
    app_lifespan.add(rpc_api_lifespan)

    # - director
    app_lifespan.add(director_lifespan)

    # - function services
    app_lifespan.add(function_services_lifespan)

    # - background task
    app_lifespan.add(background_task_lifespan)

    # - prometheus instrumentation
    app_lifespan.add(_prometheus_instrumentation_lifespan)

    app_lifespan.add(_banners_lifespan)

    return app_lifespan
