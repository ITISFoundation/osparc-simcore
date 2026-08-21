from aws_library.ec2 import EC2InstanceData, TrackedGauge
from aws_library.ec2 import create_gauge as _create_gauge
from prometheus_client import CollectorRegistry

from ...utils.ec2 import user_id_from_instance_tags, wallet_id_from_instance_tags
from ._constants import METRICS_NAMESPACE


def _instance_labels(instance: EC2InstanceData) -> tuple[str, str, str]:
    return (
        f"{instance.type}",
        f"{user_id_from_instance_tags(instance.tags)}",
        f"{wallet_id_from_instance_tags(instance.tags)}",
    )


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
        label_extractor=_instance_labels,
    )
