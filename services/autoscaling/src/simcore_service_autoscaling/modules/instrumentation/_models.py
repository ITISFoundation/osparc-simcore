from dataclasses import dataclass, field
from typing import Final

from prometheus_client import CollectorRegistry, Counter, Histogram
from servicelib.instrumentation import MetricsBase

from ...models import Cluster, WarmBufferPoolManager
from ._constants import (
    CLUSTER_METRICS_DEFINITIONS,
    EC2_INSTANCE_LABELS,
    METRICS_NAMESPACE,
    WARM_BUFFER_POOLS_METRICS_DEFINITIONS,
)
from ._utils import TrackedGauge, create_gauge


@dataclass(slots=True, kw_only=True)
class ClusterMetrics(MetricsBase):  # pylint: disable=too-many-instance-attributes
    active_nodes: TrackedGauge = field(init=False)
    pending_nodes: TrackedGauge = field(init=False)
    drained_nodes: TrackedGauge = field(init=False)
    hot_buffer_drained_nodes: TrackedGauge = field(init=False)
    pending_ec2s: TrackedGauge = field(init=False)
    broken_ec2s: TrackedGauge = field(init=False)
    warm_buffer_ec2s: TrackedGauge = field(init=False)
    disconnected_nodes: TrackedGauge = field(init=False)
    terminating_nodes: TrackedGauge = field(init=False)
    retired_nodes: TrackedGauge = field(init=False)
    terminated_instances: TrackedGauge = field(init=False)

    def __post_init__(self) -> None:
        cluster_subsystem = f"{self.subsystem}_cluster"
        # Creating and assigning gauges using the field names and the metric definitions
        for field_name, definition in CLUSTER_METRICS_DEFINITIONS.items():
            gauge = create_gauge(
                field_name=field_name,
                definition=definition,
                subsystem=cluster_subsystem,
                registry=self.registry,
            )
            setattr(self, field_name, gauge)

    def update_from_cluster(self, cluster: Cluster) -> None:
        for field_name in CLUSTER_METRICS_DEFINITIONS:
            if field_name != "disconnected_nodes":
                tracked_gauge = getattr(self, field_name)
                assert isinstance(tracked_gauge, TrackedGauge)  # nosec
                instances = getattr(cluster, field_name)
                assert isinstance(instances, list)  # nosec
                tracked_gauge.update_from_instances(i.ec2_instance for i in instances)
            else:
                self.disconnected_nodes.gauge.set(len(cluster.disconnected_nodes))


@dataclass(slots=True, kw_only=True)
class EC2ClientMetrics(MetricsBase):
    launched_instances: Counter = field(init=False)
    started_instances: Counter = field(init=False)
    stopped_instances: Counter = field(init=False)
    terminated_instances: Counter = field(init=False)

    def __post_init__(self) -> None:
        self.launched_instances = Counter(
            "launched_instances_total",
            "Number of EC2 instances that were launched",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.started_instances = Counter(
            "started_instances_total",
            "Number of EC2 instances that were started",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.stopped_instances = Counter(
            "stopped_instances_total",
            "Number of EC2 instances that were stopped",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.terminated_instances = Counter(
            "terminated_instances_total",
            "Number of EC2 instances that were terminated",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )

    def instance_started(self, instance_type: str) -> None:
        self.started_instances.labels(instance_type=instance_type).inc()

    def instance_launched(self, instance_type: str) -> None:
        self.launched_instances.labels(instance_type=instance_type).inc()

    def instance_stopped(self, instance_type: str) -> None:
        self.stopped_instances.labels(instance_type=instance_type).inc()

    def instance_terminated(self, instance_type: str) -> None:
        self.terminated_instances.labels(instance_type=instance_type).inc()


_MINUTE: Final[int] = 60


@dataclass(slots=True, kw_only=True)
class WarmBufferPoolsMetrics(MetricsBase):
    ready_instances: TrackedGauge = field(init=False)
    pending_instances: TrackedGauge = field(init=False)
    waiting_to_pull_instances: TrackedGauge = field(init=False)
    waiting_to_stop_instances: TrackedGauge = field(init=False)
    pulling_instances: TrackedGauge = field(init=False)
    stopping_instances: TrackedGauge = field(init=False)
    broken_instances: TrackedGauge = field(init=False)

    instances_ready_to_pull_seconds: Histogram = field(init=False)
    instances_completed_pulling_seconds: Histogram = field(init=False)

    def __post_init__(self) -> None:
        buffer_pools_subsystem = f"{self.subsystem}_buffer_machines_pools"
        for field_name, definition in WARM_BUFFER_POOLS_METRICS_DEFINITIONS.items():
            setattr(
                self,
                field_name,
                create_gauge(
                    field_name=field_name,
                    definition=definition,
                    subsystem=buffer_pools_subsystem,
                    registry=self.registry,
                ),
            )
        self.instances_ready_to_pull_seconds = Histogram(
            "instances_ready_to_pull_duration_seconds",
            "Time taken for instances to be ready to pull",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=buffer_pools_subsystem,
            buckets=(10, 20, 30, 40, 50, 60, 120),
            registry=self.registry,
        )
        self.instances_completed_pulling_seconds = Histogram(
            "instances_completed_pulling_duration_seconds",
            "Time taken for instances to complete docker images pre-pulling",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=buffer_pools_subsystem,
            buckets=(
                30,
                1 * _MINUTE,
                2 * _MINUTE,
                3 * _MINUTE,
                5 * _MINUTE,
                10 * _MINUTE,
                20 * _MINUTE,
                30 * _MINUTE,
                40 * _MINUTE,
            ),
            registry=self.registry,
        )

    def update_from_buffer_pool_manager(
        self, buffer_pool_manager: WarmBufferPoolManager
    ) -> None:
        flat_pool = buffer_pool_manager.flatten_buffer_pool()

        for field_name in WARM_BUFFER_POOLS_METRICS_DEFINITIONS:
            tracked_gauge = getattr(self, field_name)
            assert isinstance(tracked_gauge, TrackedGauge)  # nosec
            instances = getattr(flat_pool, field_name)
            assert isinstance(instances, set)  # nosec
            tracked_gauge.update_from_instances(instances)


@dataclass(slots=True, kw_only=True)
class AutoscalingInstrumentation(MetricsBase):
    registry: CollectorRegistry

    cluster_metrics: ClusterMetrics = field(init=False)
    ec2_client_metrics: EC2ClientMetrics = field(init=False)
    buffer_machines_pools_metrics: WarmBufferPoolsMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.cluster_metrics = ClusterMetrics(  # pylint: disable=unexpected-keyword-arg
            subsystem=self.subsystem, registry=self.registry
        )
        self.ec2_client_metrics = EC2ClientMetrics(  # pylint: disable=unexpected-keyword-arg
            subsystem=self.subsystem, registry=self.registry
        )
        self.buffer_machines_pools_metrics = WarmBufferPoolsMetrics(  # pylint: disable=unexpected-keyword-arg
            subsystem=self.subsystem, registry=self.registry
        )
