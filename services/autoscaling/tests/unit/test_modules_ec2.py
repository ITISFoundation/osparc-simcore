# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

from collections.abc import Callable
from typing import TypedDict

import pytest
from aws_library.ec2 import EC2InstanceConfig, EC2InstanceType, Resources
from faker import Faker
from fastapi import FastAPI
from prometheus_client.metrics import MetricWrapperBase
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.core.errors import ConfigurationError
from simcore_service_autoscaling.modules.ec2 import get_ec2_client
from simcore_service_autoscaling.modules.instrumentation import (
    get_instrumentation,
    has_instrumentation,
)
from types_aiobotocore_ec2.literals import InstanceTypeType


async def test_ec2_does_not_initialize_if_deactivated(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "ec2_client")
    assert initialized_app.state.ec2_client is None
    with pytest.raises(ConfigurationError):
        get_ec2_client(initialized_app)


@pytest.fixture
def create_ec2_instance_config(
    faker: Faker,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
) -> Callable[[InstanceTypeType], EC2InstanceConfig]:
    def _(instance_type: InstanceTypeType) -> EC2InstanceConfig:
        return EC2InstanceConfig(
            type=EC2InstanceType(
                name=instance_type, resources=Resources.create_as_empty()
            ),
            tags=faker.pydict(allowed_types=(str,)),
            startup_script=faker.pystr(),
            ami_id=aws_ami_id,
            key_name=faker.pystr(),
            security_group_ids=[aws_security_group_id],
            subnet_id=aws_subnet_id,
            iam_instance_profile="",
        )

    return _


class _ExpectedSample(TypedDict):
    name: str
    value: float
    labels: dict[str, str]


def _assert_metrics(
    metrics_to_collect: MetricWrapperBase,
    *,
    expected_num_samples: int,
    check_sample_index: int | None,
    expected_sample: _ExpectedSample | None
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


async def test_ec2_with_instrumentation_enabled(
    disabled_rabbitmq: None,
    disabled_ssm: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    create_ec2_instance_config: Callable[[InstanceTypeType], EC2InstanceConfig],
    faker: Faker,
):
    assert hasattr(initialized_app.state, "ec2_client")
    assert initialized_app.state.ec2_client
    ec2_client = get_ec2_client(initialized_app)
    assert has_instrumentation(initialized_app)

    # check current metrics (should be 0)
    instrumentation = get_instrumentation(initialized_app)
    _assert_metrics(
        instrumentation._launched_instances,  # noqa: SLF001
        expected_num_samples=0,
        check_sample_index=None,
        expected_sample=None,
    )

    # create some EC2s
    a1_2xlarge_config = create_ec2_instance_config("a1.2xlarge")
    num_a1_2xlarge = faker.pyint(min_value=1, max_value=12)
    a1_2xlarge_instances = await ec2_client.launch_instances(
        a1_2xlarge_config,
        min_number_of_instances=num_a1_2xlarge,
        number_of_instances=num_a1_2xlarge,
        max_total_number_of_instances=500,
    )

    # now the metrics shall increase
    _assert_metrics(
        instrumentation._launched_instances,  # noqa: SLF001
        expected_num_samples=2,
        check_sample_index=0,
        expected_sample={
            "name": "simcore_service_autoscaling_computational_launched_instances_total",
            "value": num_a1_2xlarge,
            "labels": {"instance_type": "a1.2xlarge"},
        },
    )

    # create some other EC2s
    c5ad_12xlarge_config = create_ec2_instance_config("c5ad.12xlarge")
    num_c5ad_12xlarge = faker.pyint(min_value=1, max_value=123)
    c5ad_12xlarge_instances = await ec2_client.launch_instances(
        c5ad_12xlarge_config,
        min_number_of_instances=num_c5ad_12xlarge,
        number_of_instances=num_c5ad_12xlarge,
        max_total_number_of_instances=500,
    )
    # we should get additional metrics with different labels
    _assert_metrics(
        instrumentation._launched_instances,  # noqa: SLF001
        expected_num_samples=4,
        check_sample_index=2,
        expected_sample={
            "name": "simcore_service_autoscaling_computational_launched_instances_total",
            "value": num_c5ad_12xlarge,
            "labels": {"instance_type": "c5ad.12xlarge"},
        },
    )

    # now we stop the last ones created
    await ec2_client.stop_instances(c5ad_12xlarge_instances)

    # we get the stopped metrics increased now
    _assert_metrics(
        instrumentation._stopped_instances,  # noqa: SLF001
        expected_num_samples=2,
        check_sample_index=0,
        expected_sample={
            "name": "simcore_service_autoscaling_computational_stopped_instances_total",
            "value": num_c5ad_12xlarge,
            "labels": {"instance_type": "c5ad.12xlarge"},
        },
    )

    # we terminate them
    await ec2_client.terminate_instances(c5ad_12xlarge_instances)

    # we get the terminated metrics increased now
    _assert_metrics(
        instrumentation._terminated_instances,  # noqa: SLF001
        expected_num_samples=2,
        check_sample_index=0,
        expected_sample={
            "name": "simcore_service_autoscaling_computational_terminated_instances_total",
            "value": num_c5ad_12xlarge,
            "labels": {"instance_type": "c5ad.12xlarge"},
        },
    )

    # we terminate the rest
    await ec2_client.terminate_instances(a1_2xlarge_instances)

    # we get the terminated metrics increased now
    _assert_metrics(
        instrumentation._terminated_instances,  # noqa: SLF001
        expected_num_samples=4,
        check_sample_index=2,
        expected_sample={
            "name": "simcore_service_autoscaling_computational_terminated_instances_total",
            "value": num_a1_2xlarge,
            "labels": {"instance_type": "a1.2xlarge"},
        },
    )
