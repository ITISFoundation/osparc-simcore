from fastapi import FastAPI
from servicelib.fastapi.monitoring import (
    setup_prometheus_instrumentation,
)
from simcore_service_agent.core.settings import ApplicationSettings

from ._models import AgentInstrumentation


def setup_instrumentation(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings
    if not settings.AGENT_PROMETHEUS_INSTRUMENTATION_ENABLED:
        return

    registry = setup_prometheus_instrumentation(app)

    async def on_startup() -> None:
        app.state.instrumentation = AgentInstrumentation(registry=registry)

    app.add_event_handler("startup", on_startup)


def get_instrumentation(app: FastAPI) -> AgentInstrumentation:
    assert (
        app.state.instrumentation
    ), "Instrumentation not setup. Please check the configuration"  # nosec
    instrumentation: AgentInstrumentation = app.state.instrumentation
    return instrumentation
