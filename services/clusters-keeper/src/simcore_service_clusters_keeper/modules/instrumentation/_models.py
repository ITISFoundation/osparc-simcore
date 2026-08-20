from collections.abc import Iterable
from dataclasses import dataclass, field

from aws_library.ec2 import EC2InstanceData
from prometheus_client import CollectorRegistry
from servicelib.instrumentation import MetricsBase

from ._constants import PRIMARY_INSTANCES_METRICS_DEFINITIONS
from ._utils import TrackedGauge, create_gauge


@dataclass(slots=True, kw_only=True)
class PrimaryInstancesMetrics(MetricsBase):
    starting_instances: TrackedGauge = field(init=False)
    connected_instances: TrackedGauge = field(init=False)
    busy_instances: TrackedGauge = field(init=False)
    broken_instances: TrackedGauge = field(init=False)

    def __post_init__(self) -> None:
        # Creating and assigning gauges using the field names and the metric definitions
        for field_name, definition in PRIMARY_INSTANCES_METRICS_DEFINITIONS.items():
            gauge = create_gauge(
                field_name=field_name,
                definition=definition,
                subsystem=self.subsystem,
                registry=self.registry,
            )
            setattr(self, field_name, gauge)

    def update_from_clusters(
        self,
        *,
        starting: Iterable[EC2InstanceData],
        connected: Iterable[EC2InstanceData],
        busy: Iterable[EC2InstanceData],
        broken: Iterable[EC2InstanceData],
    ) -> None:
        self.starting_instances.update_from_instances(starting)
        self.connected_instances.update_from_instances(connected)
        self.busy_instances.update_from_instances(busy)
        self.broken_instances.update_from_instances(broken)


@dataclass(slots=True, kw_only=True)
class ClustersKeeperInstrumentation(MetricsBase):
    registry: CollectorRegistry

    primary_instances_metrics: PrimaryInstancesMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.primary_instances_metrics = PrimaryInstancesMetrics(  # pylint: disable=unexpected-keyword-arg
            subsystem="primary", registry=self.registry
        )
