from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.monitoring import configure_prometheus_instrumentation

from ...core.errors import ConfigurationError
from ._models import DirectorV2Instrumentation


async def _instrumentation_lifespan(app: FastAPI) -> AsyncIterator[State]:
    registry = app.state.prometheus_metrics.registry
    app.state.instrumentation = DirectorV2Instrumentation(registry=registry)
    yield {}


def configure_instrumentation(app: FastAPI, app_lifespan: LifespanManager) -> None:
    configure_prometheus_instrumentation(app, app_lifespan, _instrumentation_lifespan)


def get_instrumentation(app: FastAPI) -> DirectorV2Instrumentation:
    if not app.state.instrumentation:
        raise ConfigurationError(msg="Instrumentation not setup. Please check the configuration.")
    return cast(DirectorV2Instrumentation, app.state.instrumentation)
