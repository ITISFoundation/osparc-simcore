from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from ...core.errors import ConfigurationError
from ...core.settings import get_application_settings
from ._models import AutoscalingInstrumentation


async def autoscaling_instrumentation_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app_settings = get_application_settings(app)
    metrics_subsystem = "dynamic" if app_settings.AUTOSCALING_NODES_MONITORING else "computational"
    registry = app.state.prometheus_metrics.registry
    app.state.instrumentation = AutoscalingInstrumentation(  # pylint: disable=unexpected-keyword-arg
        registry=registry, subsystem=metrics_subsystem
    )
    try:
        yield {}
    finally:
        pass


def get_instrumentation(app: FastAPI) -> AutoscalingInstrumentation:
    if not hasattr(app.state, "instrumentation"):
        raise ConfigurationError(msg="Instrumentation not setup. Please check the configuration.")
    return cast(AutoscalingInstrumentation, app.state.instrumentation)


def has_instrumentation(app: FastAPI) -> bool:
    return hasattr(app.state, "instrumentation")
