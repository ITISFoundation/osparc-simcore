import collections
from collections.abc import Iterable
from dataclasses import dataclass, field

from aws_library.ec2 import EC2InstanceData
from prometheus_client import CollectorRegistry, Gauge

from ...utils.ec2 import user_id_from_instance_tags, wallet_id_from_instance_tags
from ._constants import METRICS_NAMESPACE

_InstanceLabels = tuple[str, str, str]


def _instance_labels(instance: EC2InstanceData) -> _InstanceLabels:
    return (
        f"{instance.type}",
        f"{user_id_from_instance_tags(instance.tags)}",
        f"{wallet_id_from_instance_tags(instance.tags)}",
    )


@dataclass
class TrackedGauge:
    gauge: Gauge
    _tracked_labels: set[_InstanceLabels] = field(default_factory=set)

    def update_from_instances(self, instances: Iterable[EC2InstanceData]) -> None:
        instance_counts = collections.Counter(_instance_labels(i) for i in instances)
        current_labels = set(instance_counts.keys())
        self._tracked_labels.update(current_labels)
        # update the gauge
        for (instance_type, user_id, wallet_id), count in instance_counts.items():
            self.gauge.labels(instance_type=instance_type, user_id=user_id, wallet_id=wallet_id).set(count)
        # set the unused ones to 0
        for instance_type, user_id, wallet_id in self._tracked_labels - current_labels:
            self.gauge.labels(instance_type=instance_type, user_id=user_id, wallet_id=wallet_id).set(0)


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
