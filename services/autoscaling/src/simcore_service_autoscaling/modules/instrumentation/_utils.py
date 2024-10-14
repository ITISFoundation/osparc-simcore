import collections
from collections.abc import Iterable
from dataclasses import dataclass, field

from aws_library.ec2._models import EC2InstanceData
from prometheus_client import CollectorRegistry, Gauge

from ._constants import METRICS_NAMESPACE


@dataclass
class TrackedGauge:
    gauge: Gauge
    _tracked_labels: set[str] = field(default_factory=set)

    def update_from_instances(self, instances: Iterable[EC2InstanceData]) -> None:
        # Create a Counter to count nodes by instance type
        instance_type_counts = collections.Counter(f"{i.type}" for i in instances)
        current_instance_types = set(instance_type_counts.keys())
        self._tracked_labels.update(current_instance_types)
        # update the gauge
        for instance_type, count in instance_type_counts.items():
            self.gauge.labels(instance_type=instance_type).set(count)
        # set the unused ones to 0
        for instance_type in self._tracked_labels - current_instance_types:
            self.gauge.labels(instance_type=instance_type).set(0)


def create_gauge(
    *,
    field_name: str,
    definition: tuple[str, tuple[str, ...]],
    subsystem: str,
    registry: CollectorRegistry,
) -> TrackedGauge:
    description, labelnames = definition
    return TrackedGauge(
        Gauge(
            name=field_name,
            documentation=description,
            labelnames=labelnames,
            namespace=METRICS_NAMESPACE,
            subsystem=subsystem,
            registry=registry,
        )
    )
