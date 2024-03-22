from dataclasses import dataclass, field
from typing import Final, cast

from fastapi import FastAPI
from prometheus_client import CollectorRegistry, Counter, Gauge
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation as setup_rest_instrumentation,
)

from .._meta import APP_NAME
from ..core.errors import ConfigurationError
from ..core.settings import get_application_settings
from ..models import AssociatedInstance, Cluster, NonAssociatedInstance

METRICS_NAMESPACE: Final[str] = APP_NAME.replace("-", "_")
EC2_INSTANCE_LABELS: Final[tuple[str]] = ("instance_type",)


def _update_gauge(
    gauge: Gauge,
    nodes: list[AssociatedInstance] | list[NonAssociatedInstance],
) -> None:
    gauge.clear()

    for node in nodes:
        gauge.labels(instance_type=node.ec2_instance.type).inc()


@dataclass(slots=True, kw_only=True)
class AutoscalingInstrumentation:  # pylint: disable=too-many-instance-attributes
    registry: CollectorRegistry
    subsystem: str
    _active_nodes: Gauge = field(init=False)
    _pending_nodes: Gauge = field(init=False)
    _drained_nodes: Gauge = field(init=False)
    _buffer_drained_nodes: Gauge = field(init=False)
    _pending_ec2s: Gauge = field(init=False)
    _disconnected_nodes: Gauge = field(init=False)
    _started_instances: Counter = field(init=False)
    _terminated_instances: Counter = field(init=False)

    def __post_init__(self) -> None:
        self._active_nodes = Gauge(
            "active_nodes",
            "Number of EC2-backed docker nodes which are active and ready to run tasks",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )
        self._pending_nodes = Gauge(
            "pending_nodes",
            "Number of EC2-backed docker nodes which are active and NOT ready to run tasks",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )
        self._drained_nodes = Gauge(
            "drained_nodes",
            "Number of EC2-backed docker nodes which are drained",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )
        self._buffer_drained_nodes = Gauge(
            "buffer_drained_nodes",
            "Number of EC2-backed docker nodes which are drained and in buffer/reserve",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )
        self._pending_ec2s = Gauge(
            "pending_ec2s",
            "Number of EC2 instance not yet part of the cluster",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )
        self._disconnected_nodes = Gauge(
            "disconnected_nodes",
            "Number of docker node not backed by a running EC2 instance",
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )
        self._started_instances = Counter(
            "started_instances_total",
            "Number of EC2 instances that were started",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )
        self._terminated_instances = Counter(
            "terminated_ec2_instances_total",
            "Number of EC2 instances that were terminated",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )

    def update_from_cluster(self, cluster: Cluster) -> None:
        _update_gauge(self._active_nodes, cluster.active_nodes)
        _update_gauge(self._pending_nodes, cluster.pending_nodes)
        _update_gauge(self._drained_nodes, cluster.drained_nodes)
        _update_gauge(self._buffer_drained_nodes, cluster.reserve_drained_nodes)
        _update_gauge(self._pending_ec2s, cluster.pending_ec2s)
        self._disconnected_nodes.set(len(cluster.disconnected_nodes))

    def instance_started(self, instance_type: str) -> None:
        self._started_instances.labels(instance_type=instance_type).inc()

    def instance_terminated(self, instance_type: str) -> None:
        self._terminated_instances.labels(instance_type=instance_type).inc()


def setup(app: FastAPI) -> None:
    app_settings = get_application_settings(app)
    if not app_settings.AUTOSCALING_PROMETHEUS_INSTRUMENTATION_ENABLED:
        return

    # NOTE: this must be setup before application startup
    instrumentator = setup_rest_instrumentation(app)

    async def on_startup() -> None:
        metrics_subsystem = (
            "dynamic" if app_settings.AUTOSCALING_NODES_MONITORING else "computational"
        )
        app.state.instrumentation = AutoscalingInstrumentation(
            registry=instrumentator.registry, subsystem=metrics_subsystem
        )

    async def on_shutdown() -> None:
        ...

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_instrumentation(app: FastAPI) -> AutoscalingInstrumentation:
    if not app.state.instrumentation:
        raise ConfigurationError(
            msg="Instrumentation not setup. Please check the configuration."
        )
    return cast(AutoscalingInstrumentation, app.state.instrumentation)


def has_instrumentation(app: FastAPI) -> bool:
    return hasattr(app.state, "instrumentation")
