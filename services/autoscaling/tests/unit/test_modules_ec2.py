# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

from typing import Callable

import pytest
from aws_library.ec2.models import EC2InstanceConfig, EC2InstanceType, Resources
from faker import Faker
from fastapi import FastAPI
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
                name="a1.large", resources=Resources.create_as_empty()
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


async def test_ec2_with_instrumentation_enabled(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    create_ec2_instance_config: Callable[[InstanceTypeType], EC2InstanceConfig],
):
    assert hasattr(initialized_app.state, "ec2_client")
    assert initialized_app.state.ec2_client
    ec2_client = get_ec2_client(initialized_app)
    assert has_instrumentation(initialized_app)

    instrumentation = get_instrumentation(initialized_app)
    instance_launched_metrics = list(
        instrumentation._launched_instances.collect()  # noqa: SLF001
    )
    assert len(instance_launched_metrics) == 1
    assert instance_launched_metrics[0]
    metrics = instance_launched_metrics[0]
    assert metrics.samples == []

    a1_2xlarge_config = create_ec2_instance_config("a1.2xlarge")
    await ec2_client.launch_instances(
        a1_2xlarge_config, min_number_of_instances=2, number_of_instances=2
    )
    instance_launched_metrics = list(
        instrumentation._launched_instances.collect()  # noqa: SLF001
    )
    assert len(instance_launched_metrics) == 1

    assert instance_launched_metrics[0]
    metrics = instance_launched_metrics[0]
    assert metrics.samples == [2.0]
