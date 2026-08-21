from collections.abc import Callable

from aws_library.ec2._models import EC2InstanceData
from prometheus_client import CollectorRegistry
from simcore_service_autoscaling.modules.instrumentation._constants import (
    EC2_INSTANCE_LABELS,
)
from simcore_service_autoscaling.modules.instrumentation._utils import create_gauge


def test_create_gauge_labels_instances_by_instance_type(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    # NOTE: TrackedGauge's own bookkeeping (e.g. resetting stale label combos to 0) is
    # tested once, generically, in aws-library's test_ec2_instrumentation.py. Here we only
    # check that this service's create_gauge() wrapper feeds it the expected instance_type label.
    registry = CollectorRegistry()
    tracked_gauge = create_gauge(
        field_name="example_gauge",
        definition=("An example gauge", EC2_INSTANCE_LABELS),
        subsystem="whatever",
        registry=registry,
    )

    instance = fake_ec2_instance_data()
    tracked_gauge.update_from_instances([instance])

    sample = next(iter(tracked_gauge.gauge.collect())).samples[0]
    assert sample.name == "simcore_service_autoscaling_whatever_example_gauge"
    assert sample.value == 1
    assert sample.labels == {"instance_type": instance.type}
