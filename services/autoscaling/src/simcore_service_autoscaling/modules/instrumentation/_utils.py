from aws_library.ec2 import EC2InstanceData, TrackedGauge
from aws_library.ec2 import create_gauge as _create_gauge
from prometheus_client import CollectorRegistry

from ._constants import METRICS_NAMESPACE


def _instance_type_label(instance: EC2InstanceData) -> tuple[str]:
    return (f"{instance.type}",)


def create_gauge(
    *,
    field_name: str,
    definition: tuple[str, tuple[str, ...]],
    subsystem: str,
    registry: CollectorRegistry,
) -> TrackedGauge:
    return _create_gauge(
        field_name=field_name,
        definition=definition,
        namespace=METRICS_NAMESPACE,
        subsystem=subsystem,
        registry=registry,
        label_extractor=_instance_type_label,
    )
