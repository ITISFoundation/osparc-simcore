from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.monitoring import (
    configure_prometheus_instrumentation,
)

from ...core.settings import ApplicationSettings
from ._models import AgentInstrumentation


def configure_instrumentation(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
) -> None:
    settings: ApplicationSettings = app.state.settings
    if not settings.AGENT_PROMETHEUS_INSTRUMENTATION_ENABLED:
        return

    async def _instrumentation_lifespan(lifespan_app: FastAPI) -> AsyncIterator[State]:
        app.state.instrumentation = AgentInstrumentation(registry=lifespan_app.state.prometheus_metrics.registry)
        yield {}

    configure_prometheus_instrumentation(
        app,
        app_lifespan,
        _instrumentation_lifespan,
    )


def get_instrumentation(app: FastAPI) -> AgentInstrumentation:
    assert app.state.instrumentation, "Instrumentation not setup. Please check the configuration"  # nosec
    instrumentation: AgentInstrumentation = app.state.instrumentation
    return instrumentation
