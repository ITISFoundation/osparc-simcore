import collections
from collections.abc import Iterable

from aws_library.ec2._models import EC2InstanceData
from prometheus_client import Gauge

from ._constants import METRICS_NAMESPACE


def create_gauge(
    field_name: str, definition: tuple[str, tuple[str, ...]], subsystem: str
) -> Gauge:
    description, labelnames = definition
    return Gauge(
        name=field_name,
        documentation=description,
        labelnames=labelnames,
        namespace=METRICS_NAMESPACE,
        subsystem=subsystem,
    )


def update_gauge(
    gauge: Gauge,
    instances: Iterable[EC2InstanceData],
) -> None:
    gauge.clear()
    # Create a Counter to count nodes by instance type
    instance_type_counts = collections.Counter(i.type for i in instances)

    # Set the gauge for each instance type to the count
    for instance_type, count in instance_type_counts.items():
        gauge.labels(instance_type=instance_type).set(count)
