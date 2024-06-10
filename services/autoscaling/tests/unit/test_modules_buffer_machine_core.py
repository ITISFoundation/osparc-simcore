# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DockerGenericTag
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_autoscaling.modules.auto_scaling_mode_dynamic import (
    DynamicAutoscaling,
)
from simcore_service_autoscaling.modules.buffer_machine_core import (
    monitor_buffer_machines,
)


@pytest.fixture
def buffer_count(faker: Faker) -> int:
    return faker.pyint(min_value=1, max_value=9)


@pytest.fixture
def ec2_instances_boot_ami_pre_pull(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    buffer_count: int,
) -> EnvVarsDict:
    images = parse_obj_as(
        list[DockerGenericTag],
        [
            "nginx:latest",
            "itisfoundation/my-very-nice-service:latest",
            "simcore/services/dynamic/another-nice-one:2.4.5",
            "asd",
        ],
    )
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {
                    "t2.micro": {
                        "ami_id": faker.pystr(),
                        "pre_pull_images": images,
                        "buffer_count": buffer_count,
                    }
                }
            ),
        },
    )
    return app_environment | envs


async def test_monitor_buffer_machines(
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    mocked_ec2_server_envs: EnvVarsDict,
    enabled_buffer_pools: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    ec2_instances_boot_ami_pre_pull: EnvVarsDict,
    initialized_app: FastAPI,
):
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
