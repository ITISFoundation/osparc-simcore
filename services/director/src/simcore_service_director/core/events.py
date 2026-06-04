import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.httpx_client import (
    HttpxLifespanState,
    create_httpx_lifespan,
)
from servicelib.fastapi.lifespan_utils import Lifespan, lifespan_context
from servicelib.fastapi.monitoring import (
    create_prometheus_instrumentationmain_input_state,
    prometheus_instrumentation_lifespan,
)
from servicelib.fastapi.tracing import tracing_instrumentation_lifespan
from servicelib.tracing import TracingConfig

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..instrumentation import director_instrumentation_lifespan
from ..modules.docker_registry import registry_lifespan
from ..modules.redis import redis_clients_manager_lifespan
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


async def _banners_lifespan(_) -> AsyncIterator[State]:
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


async def _settings_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings

    yield {
        **create_prometheus_instrumentationmain_input_state(enabled=settings.DIRECTOR_MONITORING_ENABLED),
    }


async def httpx_set_in_app(app: FastAPI, state: State) -> AsyncIterator[State]:
    with lifespan_context(_logger, logging.INFO, f"{__name__}.{httpx_set_in_app.__name__}", state) as called_state:
        app.state.httpx_client = state[HttpxLifespanState.HTTPX_CLIENT]
        yield called_state


def create_app_lifespan(
    *,
    settings: ApplicationSettings,
    logging_lifespan: Lifespan | None,
    tracing_config: TracingConfig,
) -> LifespanManager:  # WARNING: order matters
    app_lifespan = LifespanManager()
    if logging_lifespan:
        app_lifespan.add(logging_lifespan)

    app_lifespan.add(_settings_lifespan)
    if tracing_config.tracing_enabled:
        app_lifespan.add(tracing_instrumentation_lifespan(tracing_config=tracing_config))

    app_lifespan.add(
        create_httpx_lifespan(
            max_keepalive_connections=settings.DIRECTOR_REGISTRY_CLIENT_MAX_KEEPALIVE_CONNECTIONS,
            default_timeout=settings.DIRECTOR_REGISTRY_CLIENT_TIMEOUT,
            tracing_config=tracing_config,
        )
    )
    app_lifespan.add(httpx_set_in_app)

    if settings.DIRECTOR_REGISTRY_CACHING:
        app_lifespan.add(redis_clients_manager_lifespan)
    app_lifespan.add(registry_lifespan)

    app_lifespan.add(prometheus_instrumentation_lifespan)
    app_lifespan.add(director_instrumentation_lifespan)
    app_lifespan.add(_banners_lifespan)

    return app_lifespan
