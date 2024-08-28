import collections
import functools
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass, field
from typing import Any, Final, ParamSpec, TypeVar, cast

from aws_library.ec2 import EC2InstanceData, SimcoreEC2API
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
    # Create a Counter to count nodes by instance type
    instance_type_counts = collections.Counter(node.ec2_instance.type for node in nodes)

    # Set the gauge for each instance type to the count
    for instance_type, count in instance_type_counts.items():
        gauge.labels(instance_type=instance_type).set(count)


@dataclass(slots=True, kw_only=True)
class MetricsBase:
    subsystem: str


_CLUSTER_METRICS_DEFINITIONS: Final[dict[str, tuple[str, tuple[str]]]] = {
    "active_nodes": (
        "Number of EC2-backed docker nodes which are active and ready to run tasks",
        EC2_INSTANCE_LABELS,
    ),
    "pending_nodes": (
        "Number of EC2-backed docker nodes which are active and NOT ready to run tasks",
        EC2_INSTANCE_LABELS,
    ),
    "drained_nodes": (
        "Number of EC2-backed docker nodes which are drained",
        EC2_INSTANCE_LABELS,
    ),
    "buffer_drained_nodes": (
        "Number of EC2-backed docker nodes which are drained and in buffer/reserve",
        EC2_INSTANCE_LABELS,
    ),
    "pending_ec2s": (
        "Number of EC2 instances not yet part of the cluster",
        EC2_INSTANCE_LABELS,
    ),
    "broken_ec2s": (
        "Number of EC2 instances that failed joining the cluster",
        EC2_INSTANCE_LABELS,
    ),
    "buffer_ec2s": (
        "Number of buffer EC2 instances prepared, stopped, and ready to be activated",
        EC2_INSTANCE_LABELS,
    ),
    "disconnected_nodes": (
        "Number of docker nodes not backed by a running EC2 instance",
        [],
    ),
    "terminating_nodes": (
        "Number of EC2-backed docker nodes that started the termination process",
        EC2_INSTANCE_LABELS,
    ),
    "terminated_instances": (
        "Number of EC2 instances that were terminated (they are typically visible 1 hour)",
        EC2_INSTANCE_LABELS,
    ),
}


def _create_gauge(
    field_name: str, definition: tuple[str, tuple[str]], subsystem: str
) -> Gauge:
    description, labelnames = definition
    return Gauge(
        name=field_name,
        documentation=description,
        labelnames=labelnames,
        namespace=METRICS_NAMESPACE,
        subsystem=subsystem,
    )


@dataclass(slots=True, kw_only=True)
class ClusterMetrics(MetricsBase):  # pylint: disable=too-many-instance-attributes
    _active_nodes: Gauge = field(init=False)
    _pending_nodes: Gauge = field(init=False)
    _drained_nodes: Gauge = field(init=False)
    _reserve_drained_nodes: Gauge = field(init=False)
    _pending_ec2s: Gauge = field(init=False)
    _broken_ec2s: Gauge = field(init=False)
    _buffer_ec2s: Gauge = field(init=False)
    _disconnected_nodes: Gauge = field(init=False)
    _terminating_nodes: Gauge = field(init=False)
    _terminated_instances: Gauge = field(init=False)

    def __post_init__(self) -> None:
        cluster_subsystem = f"{self.subsystem}_cluster"
        # Creating and assigning gauges using the field names and the metric definitions
        for field_name, definition in _CLUSTER_METRICS_DEFINITIONS.items():
            gauge = _create_gauge(field_name, definition, cluster_subsystem)
            setattr(self, f"_{field_name}", gauge)

    def update_from_cluster(self, cluster: Cluster) -> None:
        _update_gauge(self._active_nodes, cluster.active_nodes)
        _update_gauge(self._pending_nodes, cluster.pending_nodes)
        _update_gauge(self._drained_nodes, cluster.drained_nodes)
        _update_gauge(self._reserve_drained_nodes, cluster.reserve_drained_nodes)
        _update_gauge(self._pending_ec2s, cluster.pending_ec2s)
        _update_gauge(self._broken_ec2s, cluster.broken_ec2s)
        _update_gauge(self._buffer_ec2s, cluster.buffer_ec2s)
        self._disconnected_nodes.set(len(cluster.disconnected_nodes))
        _update_gauge(self._terminating_nodes, cluster.terminating_nodes)
        _update_gauge(self._terminated_instances, cluster.terminated_instances)


@dataclass(slots=True, kw_only=True)
class EC2ClientMetrics(MetricsBase):
    _launched_instances: Counter = field(init=False)
    _started_instances: Counter = field(init=False)
    _stopped_instances: Counter = field(init=False)
    _terminated_instances: Counter = field(init=False)

    def __post_init__(self) -> None:
        self._launched_instances = Counter(
            "launched_instances_total",
            "Number of EC2 instances that were launched",
            labelnames=EC2_INSTANCE_LABELS,
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
        self._stopped_instances = Counter(
            "stopped_instances_total",
            "Number of EC2 instances that were stopped",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )
        self._terminated_instances = Counter(
            "terminated_instances_total",
            "Number of EC2 instances that were terminated",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )

    def instance_started(self, instance_type: str) -> None:
        self._started_instances.labels(instance_type=instance_type).inc()

    def instance_launched(self, instance_type: str) -> None:
        self._launched_instances.labels(instance_type=instance_type).inc()

    def instance_stopped(self, instance_type: str) -> None:
        self._stopped_instances.labels(instance_type=instance_type).inc()

    def instance_terminated(self, instance_type: str) -> None:
        self._terminated_instances.labels(instance_type=instance_type).inc()


@dataclass(slots=True, kw_only=True)
class BufferPoolsMetrics(MetricsBase):
    _ready_instances: Gauge = field(init=False)
    _pending_instances: Gauge = field(init=False)
    _waiting_to_pull_instances: Gauge = field(init=False)
    _waiting_to_stop_instances: Gauge = field(init=False)
    _pulling_instances: Gauge = field(init=False)
    _stopping_instances: Gauge = field(init=False)
    _broken_instances: Gauge = field(init=False)

    def __post_init__(self) -> None:
        buffer_pools_subsystem = f"{self.subsystem}_buffer_machines_pools"


@dataclass(slots=True, kw_only=True)
class ScalingMetrics(MetricsBase):
    def __post_init__(self) -> None:
        scaling_subsystem = f"{self.subsystem}_scaling"


@dataclass(slots=True, kw_only=True)
class AutoscalingInstrumentation(MetricsBase):
    registry: CollectorRegistry

    cluster_metrics: ClusterMetrics = field(init=False)
    ec2_client_metrics: EC2ClientMetrics = field(init=False)
    buffer_machines_pools_metrics: BufferPoolsMetrics = field(init=False)
    scaling_metrics: ScalingMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.cluster_metrics = ClusterMetrics(subsystem=self.subsystem)
        self.ec2_client_metrics = EC2ClientMetrics(subsystem=self.subsystem)
        self.buffer_machines_pools_metrics = BufferPoolsMetrics(
            subsystem=self.subsystem
        )
        self.scaling_metrics = ScalingMetrics(subsystem=self.subsystem)


P = ParamSpec("P")
R = TypeVar("R")


def _instrumented_ec2_client_method(
    metrics_handler: Callable[[str], None],
    *,
    instance_type_from_method_arguments: Callable[..., list[str]] | None,
    instance_type_from_method_return: Callable[..., list[str]] | None,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]],
    Callable[P, Coroutine[Any, Any, R]],
]:
    def decorator(
        func: Callable[P, Coroutine[Any, Any, R]]
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            result = await func(*args, **kwargs)
            if instance_type_from_method_arguments:
                for instance_type in instance_type_from_method_arguments(
                    *args, **kwargs
                ):
                    metrics_handler(instance_type)
            elif instance_type_from_method_return:
                for instance_type in instance_type_from_method_return(result):
                    metrics_handler(instance_type)
            return result

        return wrapper

    return decorator


def _instance_type_from_instance_datas(
    instance_datas: Iterable[EC2InstanceData],
) -> list[str]:
    return [i.type for i in instance_datas]


def instrument_ec2_client_methods(
    app: FastAPI, ec2_client: SimcoreEC2API
) -> SimcoreEC2API:
    autoscaling_instrumentation = get_instrumentation(app)
    methods_to_instrument = [
        (
            "launch_instances",
            autoscaling_instrumentation.ec2_client_metrics.instance_launched,
            None,
            _instance_type_from_instance_datas,
        ),
        (
            "start_instances",
            autoscaling_instrumentation.ec2_client_metrics.instance_started,
            _instance_type_from_instance_datas,
            None,
        ),
        (
            "stop_instances",
            autoscaling_instrumentation.ec2_client_metrics.instance_stopped,
            _instance_type_from_instance_datas,
            None,
        ),
        (
            "terminate_instances",
            autoscaling_instrumentation.ec2_client_metrics.instance_terminated,
            _instance_type_from_instance_datas,
            None,
        ),
    ]
    for (
        method_name,
        metrics_handler,
        instance_types_from_args,
        instance_types_from_return,
    ) in methods_to_instrument:
        method = getattr(ec2_client, method_name, None)
        assert method is not None  # nosec
        decorated_method = _instrumented_ec2_client_method(
            metrics_handler,
            instance_type_from_method_arguments=instance_types_from_args,
            instance_type_from_method_return=instance_types_from_return,
        )(method)
        setattr(ec2_client, method_name, decorated_method)
    return ec2_client


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
