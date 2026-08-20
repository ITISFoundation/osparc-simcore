# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Callable
from typing import TypedDict

from aws_library.ec2._models import EC2InstanceData
from prometheus_client import CollectorRegistry
from prometheus_client.metrics import MetricWrapperBase
from simcore_service_clusters_keeper.constants import USER_ID_TAG_KEY, WALLET_ID_TAG_KEY
from simcore_service_clusters_keeper.modules.instrumentation._constants import (
    PRIMARY_INSTANCE_LABELS,
)
from simcore_service_clusters_keeper.modules.instrumentation._utils import create_gauge


class _ExpectedSample(TypedDict):
    name: str
    value: float
    labels: dict[str, str]


def _assert_metrics(
    metrics_to_collect: MetricWrapperBase,
    *,
    expected_num_samples: int,
    check_sample_index: int | None,
    expected_sample: _ExpectedSample | None,
) -> None:
    collected_metrics = list(metrics_to_collect.collect())
    assert len(collected_metrics) == 1
    assert collected_metrics[0]
    metrics = collected_metrics[0]
    assert len(metrics.samples) == expected_num_samples
    if expected_num_samples > 0:
        assert check_sample_index is not None
        assert expected_sample is not None
        sample_1 = metrics.samples[check_sample_index]
        assert sample_1.name == expected_sample["name"]
        assert sample_1.value == expected_sample["value"]
        assert sample_1.labels == expected_sample["labels"]


def test_update_gauge_sets_old_entries_to_0(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    registry = CollectorRegistry()
    tracked_gauge = create_gauge(
        field_name="example_gauge",
        definition=("An example gauge", PRIMARY_INSTANCE_LABELS),
        subsystem="whatever",
        registry=registry,
    )

    instance_1 = fake_ec2_instance_data(tags={f"{USER_ID_TAG_KEY}": "12", f"{WALLET_ID_TAG_KEY}": "None"})

    # Update the gauge with some values
    tracked_gauge.update_from_instances([instance_1])
    _assert_metrics(
        tracked_gauge.gauge,
        expected_num_samples=1,
        check_sample_index=0,
        expected_sample=_ExpectedSample(
            name="simcore_service_clusters_keeper_whatever_example_gauge",
            value=1,
            labels={
                "instance_type": instance_1.type,
                "user_id": "12",
                "wallet_id": "None",
            },
        ),
    )

    # ensure we show an explicit 0 so that prometheus correctly updates
    instance_2 = fake_ec2_instance_data(tags={f"{USER_ID_TAG_KEY}": "35", f"{WALLET_ID_TAG_KEY}": "None"})
    assert instance_1.type != instance_2.type
    tracked_gauge.update_from_instances([instance_2])
    _assert_metrics(
        tracked_gauge.gauge,
        expected_num_samples=2,
        check_sample_index=0,
        expected_sample=_ExpectedSample(
            name="simcore_service_clusters_keeper_whatever_example_gauge",
            value=0,
            labels={
                "instance_type": instance_1.type,
                "user_id": "12",
                "wallet_id": "None",
            },
        ),
    )
