import pytest
from aws_library.ec2._errors import EC2TooManyInstancesError
from aws_library.ec2._models import EC2InstanceType, Resources
from fastapi import FastAPI
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import InstanceToLaunch
from simcore_service_autoscaling.modules.ec2 import get_ec2_client
from simcore_service_autoscaling.utils.capacity_distribution import cap_needed_instances


def _build_needed_instances(names_and_counts: list[tuple[str, int]]):
    """Helper to create an ordered mapping of InstanceToLaunch -> count."""
    return {
        InstanceToLaunch(
            instance_type=EC2InstanceType(
                name=name, resources=Resources.create_as_empty()
            ),
            node_labels={},
        ): count
        for name, count in names_and_counts
    }


async def test_cap_needed_instances_no_capping(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    assert (
        max_instances >= 3
    ), "test cannot be run with this limit, please adjust your configuration"  # Ensure we have enough for the test
    # Ensure the requested total fits in the max boundary
    needed_instances = _build_needed_instances([("t2.micro", 1), ("t3.medium", 1)])

    result = await cap_needed_instances(
        initialized_app,
        needed_instances,
        ec2_tags={},
    )

    assert result == needed_instances
    assert sum(result.values()) == 2
    assert max_instances >= 1 + 2


async def test_cap_needed_instances_minimal_cap(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
    mocker: MockerFixture,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    assert (
        max_instances >= 3
    ), "test cannot be run with this limit, please adjust your configuration"  # Ensure we have enough for the test

    # Force creatable < number of types (3 types, creatable 2)
    simcore_ec2_api = get_ec2_client(initialized_app)
    current = max_instances - 2
    mocker.patch.object(
        simcore_ec2_api,
        "get_instances",
        return_value=[{}] * current,
    )
    needed_instances = _build_needed_instances(
        [("t2.micro", 3), ("t3.medium", 2), ("m5.large", 1)]
    )

    result = await cap_needed_instances(
        initialized_app,
        needed_instances,
        ec2_tags={},
    )

    assert sum(result.values()) == 2
    # Minimal cap keeps first batches, one each
    keys = list(result.keys())
    assert keys[0].instance_type.name == "t2.micro"
    assert keys[1].instance_type.name == "t3.medium"
    assert list(result.values()) == [1, 1]


async def test_cap_needed_instances_proportional_cap(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
    mocker: MockerFixture,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    desired_creatable = 4
    assert (
        max_instances >= desired_creatable
    ), "test cannot be run with this limit, please adjust your configuration"
    simcore_ec2_api = get_ec2_client(initialized_app)
    mocker.patch.object(
        simcore_ec2_api,
        "get_instances",
        return_value=[{}] * (max_instances - desired_creatable),
    )
    needed_instances = _build_needed_instances([("t2.micro", 3), ("t3.medium", 3)])

    result = await cap_needed_instances(
        initialized_app,
        needed_instances,
        ec2_tags={},
    )

    assert sum(result.values()) == desired_creatable


async def test_cap_needed_instances_already_at_max_raises(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
    mocker: MockerFixture,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    # Already at max -> raises
    simcore_ec2_api = get_ec2_client(initialized_app)
    mocker.patch.object(
        simcore_ec2_api,
        "get_instances",
        return_value=[{}] * (max_instances),
    )

    needed_instances = _build_needed_instances([("t2.micro", 1)])

    with pytest.raises(EC2TooManyInstancesError):
        await cap_needed_instances(
            initialized_app,
            needed_instances,
            ec2_tags={},
        )
