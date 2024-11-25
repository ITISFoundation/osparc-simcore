from dataclasses import dataclass, field
from typing import cast

from fastapi import FastAPI
from prometheus_client import CollectorRegistry, Counter
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from servicelib.instrumentation import MetricsBase, get_metrics_namespace

from ._meta import APP_NAME
from .core.errors import ConfigurationError
from .core.settings import get_application_settings

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


def setup(app: FastAPI) -> None:
    app_settings = get_application_settings(app)
    if not app_settings.DIRECTOR_MONITORING_ENABLED:
        return

    # NOTE: this must be setup before application startup
    instrumentator = setup_prometheus_instrumentation(app)

    async def on_startup() -> None:
        metrics_subsystem = ""
        app.state.instrumentation = DirectorV0Instrumentation(
            registry=instrumentator.registry, subsystem=metrics_subsystem
        )

    async def on_shutdown() -> None:
        ...

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_instrumentation(app: FastAPI) -> DirectorV0Instrumentation:
    if not app.state.instrumentation:
        raise ConfigurationError(
            msg="Instrumentation not setup. Please check the configuration."
        )
    return cast(DirectorV0Instrumentation, app.state.instrumentation)


def has_instrumentation(app: FastAPI) -> bool:
    return hasattr(app.state, "instrumentation")
