import functools
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass, field
from typing import Any, Final, ParamSpec, TypeVar, cast

from aws_library.ec2.client import SimcoreEC2API
from aws_library.ec2.models import EC2InstanceData
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
class MetricsBase:
    subsystem: str


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
        self._active_nodes = Gauge(
            "active_nodes",
            "Number of EC2-backed docker nodes which are active and ready to run tasks",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=cluster_subsystem,
        )
        self._pending_nodes = Gauge(
            "pending_nodes",
            "Number of EC2-backed docker nodes which are active and NOT ready to run tasks",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=cluster_subsystem,
        )
        self._drained_nodes = Gauge(
            "drained_nodes",
            "Number of EC2-backed docker nodes which are drained",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=cluster_subsystem,
        )
        self._reserve_drained_nodes = Gauge(
            "buffer_drained_nodes",
            "Number of EC2-backed docker nodes which are drained and in buffer/reserve",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=cluster_subsystem,
        )
        self._pending_ec2s = Gauge(
            "pending_ec2s",
            "Number of EC2 instance not yet part of the cluster",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=cluster_subsystem,
        )
        self._broken_ec2s = Gauge(
            "broken_ec2s",
            "Number of EC2 instance that failed joining the cluster",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=cluster_subsystem,
        )
        self._buffer_ec2s = Gauge(
            "buffer_ec2s",
            "Number of buffer EC2 instance prepared, stopped and ready to to be activated",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=cluster_subsystem,
        )
        self._disconnected_nodes = Gauge(
            "disconnected_nodes",
            "Number of docker node not backed by a running EC2 instance",
            namespace=METRICS_NAMESPACE,
            subsystem=cluster_subsystem,
        )
        self._terminating_nodes = Gauge(
            "terminating_nodes",
            "Number of EC2-backed docker nodes that started the termination process",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=cluster_subsystem,
        )
        self._terminated_instances = Gauge(
            "terminated_instances",
            "Number of EC2 instances that were terminated (they are typically visible 1 hour)",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=cluster_subsystem,
        )

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
class AutoscalingInstrumentation(MetricsBase):
    registry: CollectorRegistry

    _cluster_metrics: ClusterMetrics = field(init=False)
    _launched_instances: Counter = field(init=False)
    _started_instances: Counter = field(init=False)
    _stopped_instances: Counter = field(init=False)
    _terminated_instances: Counter = field(init=False)

    def __post_init__(self) -> None:
        self._cluster_metrics = ClusterMetrics(subsystem=self.subsystem)
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

    def update_from_cluster(self, cluster: Cluster) -> None:
        self._cluster_metrics.update_from_cluster(cluster)

    def instance_started(self, instance_type: str) -> None:
        self._started_instances.labels(instance_type=instance_type).inc()

    def instance_launched(self, instance_type: str) -> None:
        self._launched_instances.labels(instance_type=instance_type).inc()

    def instance_stopped(self, instance_type: str) -> None:
        self._stopped_instances.labels(instance_type=instance_type).inc()

    def instance_terminated(self, instance_type: str) -> None:
        self._terminated_instances.labels(instance_type=instance_type).inc()


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
            autoscaling_instrumentation.instance_launched,
            None,
            _instance_type_from_instance_datas,
        ),
        (
            "stop_instances",
            autoscaling_instrumentation.instance_stopped,
            _instance_type_from_instance_datas,
            None,
        ),
        (
            "terminate_instances",
            autoscaling_instrumentation.instance_terminated,
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
