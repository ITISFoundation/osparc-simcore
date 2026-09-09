# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import Callable
from typing import TypedDict, cast
from unittest.mock import AsyncMock, Mock

import pytest
from aws_library.ec2 import EC2InstanceData, SimcoreEC2API
from aws_library.ec2._instrumentation import (
    EC2ClientMetrics,
    _instrumented_ec2_client_method,
    create_gauge,
    create_instrumented_ec2_client,
    instrument_ec2_client,
)
from prometheus_client import CollectorRegistry
from prometheus_client.metrics import MetricWrapperBase
from pytest_mock import MockerFixture


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
    # Create a Gauge with example labels
    registry = CollectorRegistry()
    tracked_gauge = create_gauge(
        field_name="example_gauge",
        definition=("An example gauge", ("instance_type",)),
        namespace="test_namespace",
        subsystem="whatever",
        registry=registry,
        label_extractor=lambda instance: (f"{instance.type}",),
    )

    ec2_instance_type_1 = fake_ec2_instance_data()

    # Update the gauge with some values
    tracked_gauge.update_from_instances([ec2_instance_type_1])
    _assert_metrics(
        tracked_gauge.gauge,
        expected_num_samples=1,
        check_sample_index=0,
        expected_sample=_ExpectedSample(
            name="test_namespace_whatever_example_gauge",
            value=1,
            labels={"instance_type": ec2_instance_type_1.type},
        ),
    )

    # ensure we show an explicit 0 so that prometheus correctly updates
    ec2_instance_type_2 = fake_ec2_instance_data()
    assert ec2_instance_type_1.type != ec2_instance_type_2.type
    tracked_gauge.update_from_instances([ec2_instance_type_2])
    _assert_metrics(
        tracked_gauge.gauge,
        expected_num_samples=2,
        check_sample_index=0,
        expected_sample=_ExpectedSample(
            name="test_namespace_whatever_example_gauge",
            value=0,
            labels={"instance_type": ec2_instance_type_1.type},
        ),
    )
    _assert_metrics(
        tracked_gauge.gauge,
        expected_num_samples=2,
        check_sample_index=1,
        expected_sample=_ExpectedSample(
            name="test_namespace_whatever_example_gauge",
            value=1,
            labels={"instance_type": ec2_instance_type_2.type},
        ),
    )


class _FakeEC2Client:
    """minimal stand-in exposing only the lifecycle methods instrument_ec2_client wraps"""

    def __init__(self, *, returned_instances: list[EC2InstanceData]) -> None:
        self.launch_instances = AsyncMock(return_value=returned_instances)
        self.start_instances = AsyncMock(return_value=returned_instances)
        self.stop_instances = AsyncMock(return_value=None)
        self.terminate_instances = AsyncMock(return_value=None)


async def test_instrument_ec2_client_reports_all_lifecycle_methods(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    registry = CollectorRegistry()
    metrics = EC2ClientMetrics(namespace="test_namespace", subsystem="whatever", registry=registry)  # pylint: disable=unexpected-keyword-arg
    instance = fake_ec2_instance_data()
    fake_client = cast(SimcoreEC2API, _FakeEC2Client(returned_instances=[instance]))
    ec2_client = instrument_ec2_client(fake_client, metrics)

    for method_name, tracked_counter, expected_metric_name in (
        ("launch_instances", metrics.launched_instances, "test_namespace_whatever_launched_instances_total"),
        ("start_instances", metrics.started_instances, "test_namespace_whatever_started_instances_total"),
        ("stop_instances", metrics.stopped_instances, "test_namespace_whatever_stopped_instances_total"),
        ("terminate_instances", metrics.terminated_instances, "test_namespace_whatever_terminated_instances_total"),
    ):
        await getattr(ec2_client, method_name)([instance])
        _assert_metrics(
            tracked_counter,
            expected_num_samples=2,  # Counter samples include an implicit "_created" timestamp sample
            check_sample_index=0,
            expected_sample=_ExpectedSample(
                name=expected_metric_name,
                value=1,
                labels={"instance_type": instance.type},
            ),
        )


async def test_instrument_ec2_client_skips_missing_methods(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    # future-proofing: an older/partial SimcoreEC2API missing one of the lifecycle
    # methods must not break instrumentation of the remaining ones
    registry = CollectorRegistry()
    metrics = EC2ClientMetrics(namespace="test_namespace", subsystem="whatever", registry=registry)  # pylint: disable=unexpected-keyword-arg
    instance = fake_ec2_instance_data()

    class _PartialEC2Client:
        def __init__(self) -> None:
            self.launch_instances = AsyncMock(return_value=[instance])
            # NOTE: start_instances/stop_instances/terminate_instances are intentionally missing

    fake_client = cast(SimcoreEC2API, _PartialEC2Client())
    ec2_client = instrument_ec2_client(fake_client, metrics)

    await ec2_client.launch_instances()
    _assert_metrics(
        metrics.launched_instances,
        expected_num_samples=2,
        check_sample_index=0,
        expected_sample=_ExpectedSample(
            name="test_namespace_whatever_launched_instances_total",
            value=1,
            labels={"instance_type": instance.type},
        ),
    )
    assert not hasattr(ec2_client, "start_instances")


async def test_instrumented_ec2_client_method_without_any_instance_type_source_reports_nothing(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    # covers the (unused in practice, but supported) case where neither the method
    # arguments nor its return value are used to report instance types
    metrics_handler = Mock()
    instance = fake_ec2_instance_data()

    async def _some_method(*_args, **_kwargs) -> EC2InstanceData:
        return instance

    decorated = _instrumented_ec2_client_method(
        metrics_handler,
        instance_type_from_method_arguments=None,
        instance_type_from_method_return=None,
    )(_some_method)

    result = await decorated()

    assert result is instance
    metrics_handler.assert_not_called()


async def test_create_instrumented_ec2_client_without_metrics(mocker: MockerFixture):
    mock_client = mocker.AsyncMock(spec=SimcoreEC2API)
    mocker.patch.object(SimcoreEC2API, "create", return_value=mock_client)

    result = await create_instrumented_ec2_client(mocker.Mock(), None)

    assert result is mock_client
    mock_client.close.assert_not_called()


async def test_create_instrumented_ec2_client_closes_client_if_instrumentation_wiring_fails(
    mocker: MockerFixture,
):
    # the client is created successfully (holding real resources) but wiring
    # instrumentation onto it fails afterwards: it must still be closed, not leaked
    mock_client = mocker.AsyncMock(spec=SimcoreEC2API)
    mocker.patch.object(SimcoreEC2API, "create", return_value=mock_client)
    mocker.patch(
        "aws_library.ec2._instrumentation.instrument_ec2_client",
        side_effect=RuntimeError("boom"),
    )

    with pytest.raises(RuntimeError, match="boom"):
        await create_instrumented_ec2_client(mocker.Mock(), mocker.Mock())

    mock_client.close.assert_called_once()
