# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from typing import Any

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DockerGenericTag
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_aws_ec2 import (
    assert_autoscaled_dynamic_warm_pools_ec2_instances,
)
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_autoscaling.modules.auto_scaling_mode_dynamic import (
    DynamicAutoscaling,
)
from simcore_service_autoscaling.modules.buffer_machine_core import (
    monitor_buffer_machines,
)
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType


@pytest.fixture
def buffer_count(faker: Faker) -> int:
    return faker.pyint(min_value=1, max_value=9)


@pytest.fixture
def pre_pull_images() -> list[DockerGenericTag]:
    return parse_obj_as(
        list[DockerGenericTag],
        [
            "nginx:latest",
            "itisfoundation/my-very-nice-service:latest",
            "simcore/services/dynamic/another-nice-one:2.4.5",
            "asd",
        ],
    )


@pytest.fixture
def ec2_instances_allowed_types(
    faker: Faker, pre_pull_images: list[DockerGenericTag], buffer_count: int
) -> dict[InstanceTypeType, Any]:
    return {
        "t2.micro": {
            "ami_id": faker.pystr(),
            "pre_pull_images": pre_pull_images,
            "buffer_count": buffer_count,
        }
    }


@pytest.fixture
def ec2_instance_allowed_types_env(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    ec2_instances_allowed_types: dict[InstanceTypeType, Any],
) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(ec2_instances_allowed_types),
        },
    )
    return app_environment | envs


async def test_monitor_buffer_machines(
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    mocked_ec2_instances_envs: EnvVarsDict,
    mocked_ec2_server_envs: EnvVarsDict,
    enabled_buffer_pools: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    ec2_instance_allowed_types_env: EnvVarsDict,
    initialized_app: FastAPI,
    ec2_client: EC2Client,
    ec2_instances_allowed_types: dict[InstanceTypeType, Any],
    buffer_count: int,
):
    # 0. we have no instances now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # 1. run, this will create as many buffer machines as needed
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count,
        expected_instance_type=next(iter(ec2_instances_allowed_types)),
        expected_instance_state="running",
        expected_additional_tag_keys=[],
    )

    # 2. this should now run a SSM command for pulling
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count,
        expected_instance_type=next(iter(ec2_instances_allowed_types)),
        expected_instance_state="running",
        expected_additional_tag_keys=["pulling", "ssm-command-id"],
    )

    # 3. is the command finished?
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count,
        expected_instance_type=next(iter(ec2_instances_allowed_types)),
        expected_instance_state="stopped",
        expected_additional_tag_keys=[],
    )
