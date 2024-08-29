from dataclasses import dataclass, field

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from ...models import BufferPoolManager, Cluster
from ._constants import (
    BUFFER_POOLS_METRICS_DEFINITIONS,
    CLUSTER_METRICS_DEFINITIONS,
    EC2_INSTANCE_LABELS,
    METRICS_NAMESPACE,
)
from ._utils import create_gauge, update_gauge


@dataclass(slots=True, kw_only=True)
class MetricsBase:
    subsystem: str


@dataclass(slots=True, kw_only=True)
class ClusterMetrics(MetricsBase):  # pylint: disable=too-many-instance-attributes
    active_nodes: Gauge = field(init=False)
    pending_nodes: Gauge = field(init=False)
    drained_nodes: Gauge = field(init=False)
    buffer_drained_nodes: Gauge = field(init=False)
    pending_ec2s: Gauge = field(init=False)
    broken_ec2s: Gauge = field(init=False)
    buffer_ec2s: Gauge = field(init=False)
    disconnected_nodes: Gauge = field(init=False)
    terminating_nodes: Gauge = field(init=False)
    terminated_instances: Gauge = field(init=False)

    def __post_init__(self) -> None:
        cluster_subsystem = f"{self.subsystem}_cluster"
        # Creating and assigning gauges using the field names and the metric definitions
        for field_name, definition in CLUSTER_METRICS_DEFINITIONS.items():
            gauge = create_gauge(field_name, definition, cluster_subsystem)
            setattr(self, field_name, gauge)

    def update_from_cluster(self, cluster: Cluster) -> None:
        for field_name in CLUSTER_METRICS_DEFINITIONS:
            if field_name != "disconnected_nodes":
                update_gauge(
                    getattr(self, field_name),
                    (i.ec2_instance for i in getattr(cluster, field_name)),
                )
            else:
                self.disconnected_nodes.set(len(cluster.disconnected_nodes))


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
        )
        self.started_instances = Counter(
            "started_instances_total",
            "Number of EC2 instances that were started",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )
        self.stopped_instances = Counter(
            "stopped_instances_total",
            "Number of EC2 instances that were stopped",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )
        self.terminated_instances = Counter(
            "terminated_instances_total",
            "Number of EC2 instances that were terminated",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=self.subsystem,
        )

    def instance_started(self, instance_type: str) -> None:
        self.started_instances.labels(instance_type=instance_type).inc()

    def instance_launched(self, instance_type: str) -> None:
        self.launched_instances.labels(instance_type=instance_type).inc()

    def instance_stopped(self, instance_type: str) -> None:
        self.stopped_instances.labels(instance_type=instance_type).inc()

    def instance_terminated(self, instance_type: str) -> None:
        self.terminated_instances.labels(instance_type=instance_type).inc()


@dataclass(slots=True, kw_only=True)
class BufferPoolsMetrics(MetricsBase):
    ready_instances: Gauge = field(init=False)
    pending_instances: Gauge = field(init=False)
    waiting_to_pull_instances: Gauge = field(init=False)
    waiting_to_stop_instances: Gauge = field(init=False)
    pulling_instances: Gauge = field(init=False)
    stopping_instances: Gauge = field(init=False)
    broken_instances: Gauge = field(init=False)

    instances_ready_to_pull_seconds: Histogram = field(init=False)
    instances_completed_pulling_seconds: Histogram = field(init=False)

    def __post_init__(self) -> None:
        buffer_pools_subsystem = f"{self.subsystem}_buffer_machines_pools"
        for field_name, definition in BUFFER_POOLS_METRICS_DEFINITIONS.items():
            setattr(
                self,
                field_name,
                create_gauge(field_name, definition, buffer_pools_subsystem),
            )
        self.instances_ready_to_pull_seconds = Histogram(
            "instances_ready_to_pull_seconds",
            "Time taken for instances to be ready to pull",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=buffer_pools_subsystem,
        )
        self.instances_completed_pulling_seconds = Histogram(
            "instances_completed_pulling_seconds",
            "Time taken for instances to complete docker images pre-pulling",
            labelnames=EC2_INSTANCE_LABELS,
            namespace=METRICS_NAMESPACE,
            subsystem=buffer_pools_subsystem,
        )

    def update_from_buffer_pool_manager(
        self, buffer_pool_manager: BufferPoolManager
    ) -> None:
        for buffer_pool in buffer_pool_manager.buffer_pools.values():
            for field_name in BUFFER_POOLS_METRICS_DEFINITIONS:
                update_gauge(
                    getattr(self, field_name), getattr(buffer_pool, field_name)
                )


@dataclass(slots=True, kw_only=True)
class AutoscalingInstrumentation(MetricsBase):
    registry: CollectorRegistry

    cluster_metrics: ClusterMetrics = field(init=False)
    ec2_client_metrics: EC2ClientMetrics = field(init=False)
    buffer_machines_pools_metrics: BufferPoolsMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.cluster_metrics = ClusterMetrics(subsystem=self.subsystem)
        self.ec2_client_metrics = EC2ClientMetrics(subsystem=self.subsystem)
        self.buffer_machines_pools_metrics = BufferPoolsMetrics(
            subsystem=self.subsystem
        )
