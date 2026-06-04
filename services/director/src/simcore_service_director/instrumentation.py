from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from prometheus_client import CollectorRegistry, Counter
from servicelib.instrumentation import MetricsBase, get_metrics_namespace

from ._meta import APP_NAME
from .core.errors import ConfigurationError

MONITOR_SERVICE_STARTED_LABELS: list[str] = [
    "service_key",
    "service_tag",
    "simcore_user_agent",
]

MONITOR_SERVICE_STOPPED_LABELS: list[str] = [
    "service_key",
    "service_tag",
    "result",
    "simcore_user_agent",
]


@dataclass(slots=True, kw_only=True)
class DirectorV0Instrumentation(MetricsBase):
    registry: CollectorRegistry

    services_started: Counter = field(init=False)
    services_stopped: Counter = field(init=False)

    def __post_init__(self) -> None:
        self.services_started = Counter(
            name="services_started_total",
            documentation="Counts the services started",
            labelnames=MONITOR_SERVICE_STARTED_LABELS,
            namespace=get_metrics_namespace(APP_NAME),
            subsystem=self.subsystem,
            registry=self.registry,
        )

        self.services_stopped = Counter(
            name="services_stopped_total",
            documentation="Counts the services stopped",
            labelnames=MONITOR_SERVICE_STOPPED_LABELS,
            namespace=get_metrics_namespace(APP_NAME),
            subsystem=self.subsystem,
            registry=self.registry,
        )


async def director_instrumentation_lifespan(app: FastAPI) -> AsyncIterator[State]:
    try:
        registry = app.state.prometheus_metrics.registry
        metrics_subsystem = ""
        app.state.instrumentation = DirectorV0Instrumentation(registry=registry, subsystem=metrics_subsystem)
        yield {}
    finally:
        pass


def get_instrumentation(app: FastAPI) -> DirectorV0Instrumentation:
    if not app.state.instrumentation:
        raise ConfigurationError(msg="Instrumentation not setup. Please check the configuration.")
    return cast(DirectorV0Instrumentation, app.state.instrumentation)


def has_instrumentation(app: FastAPI) -> bool:
    return hasattr(app.state, "instrumentation")
