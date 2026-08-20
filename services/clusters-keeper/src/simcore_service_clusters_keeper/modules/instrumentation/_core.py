from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from ...core.errors import ConfigurationError
from ._models import ClustersKeeperInstrumentation


async def _clusters_keeper_instrumentation_lifespan(app: FastAPI) -> AsyncIterator[State]:
    registry = app.state.prometheus_metrics.registry
    app.state.instrumentation = ClustersKeeperInstrumentation(  # pylint: disable=unexpected-keyword-arg
        registry=registry, subsystem=""
    )
    try:
        yield {}
    finally:
        pass


def configure_clusters_keeper_instrumentation(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_clusters_keeper_instrumentation_lifespan)


def get_instrumentation(app: FastAPI) -> ClustersKeeperInstrumentation:
    if not hasattr(app.state, "instrumentation"):
        raise ConfigurationError(msg="Instrumentation not setup. Please check the configuration.")
    return cast(ClustersKeeperInstrumentation, app.state.instrumentation)


def has_instrumentation(app: FastAPI) -> bool:
    return hasattr(app.state, "instrumentation")
