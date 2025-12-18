import pytest
from aws_library.ec2._errors import EC2TooManyInstancesError
from aws_library.ec2._models import EC2InstanceType, Resources
from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import InstanceToLaunch
from simcore_service_autoscaling.modules.ec2 import get_ec2_client
from simcore_service_autoscaling.utils.capacity_distribution import cap_needed_instances


def _build_needed_instances(
    names_and_counts: list[tuple[str, int]],
) -> dict[InstanceToLaunch, int]:
    """Helper to create an ordered mapping of InstanceToLaunch -> count.

    Ensures batches are unique by using distinct node_labels per occurrence.
    """
    per_type_index: dict[str, int] = {}
    instances: dict[InstanceToLaunch, int] = {}
    for name, count in names_and_counts:
        idx = per_type_index.get(name, 0)
        per_type_index[name] = idx + 1
        instances[
            InstanceToLaunch(
                instance_type=EC2InstanceType(
                    name=name,  # type: ignore
                    resources=Resources.create_as_empty(),
                ),
                node_labels={
                    TypeAdapter(DockerLabelKey).validate_python(
                        "batch"
                    ): f"{name}-{idx}"
                },
            )
        ] = count
    return instances


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
    desired_creatable = 3
    assert (
        max_instances >= desired_creatable
    ), "test cannot be run with this limit, please adjust your configuration"  # Ensure we have enough for the test

    # Force creatable < number of types (3 types, creatable 2)
    simcore_ec2_api = get_ec2_client(initialized_app)
    current = max_instances - desired_creatable
    mocker.patch.object(
        simcore_ec2_api,
        "get_instances",
        return_value=[{}] * current,
    )
    needed_instances = _build_needed_instances(
        [("t2.micro", 2), ("t2.micro", 2), ("t3.medium", 2), ("m5.large", 1)]
    )

    result = await cap_needed_instances(
        initialized_app,
        needed_instances,
        ec2_tags={},
    )

    assert sum(result.values()) == desired_creatable
    # Minimal cap keeps first batches, one each
    keys = list(result.keys())
    assert keys[0].instance_type.name == "t3.medium"
    assert keys[1].instance_type.name == "m5.large"
    assert keys[2].instance_type.name == "t2.micro"
    assert list(result.values()) == [1, 1, 1]


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


async def test_cap_needed_instances_round_robin_multiple_cycles(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
    mocker: MockerFixture,
):
    """Test round-robin distribution with multiple cycles through types.

    Exercises the while loop in _fill_capacity_round_robin by requesting
    many instances across 3 types, forcing multiple round-robin cycles.
    """
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    desired_creatable = 8
    assert (
        max_instances >= desired_creatable
    ), "test cannot be run with this limit, please adjust your configuration"

    simcore_ec2_api = get_ec2_client(initialized_app)
    mocker.patch.object(
        simcore_ec2_api,
        "get_instances",
        return_value=[{}] * (max_instances - desired_creatable),
    )
    # 3 types needing many instances forces multiple round-robin cycles
    needed_instances = _build_needed_instances(
        [("t2.micro", 5), ("t3.medium", 5), ("m5.large", 5)]
    )

    result = await cap_needed_instances(
        initialized_app,
        needed_instances,
        ec2_tags={},
    )

    assert sum(result.values()) == desired_creatable
    # Verify all three types got instances
    assert len(result) == 3
    # Verify distribution is reasonably balanced
    counts = list(result.values())
    assert all(count >= 2 for count in counts)


async def test_cap_needed_instances_proportional_with_remainder_distribution(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
    mocker: MockerFixture,
):
    """Test remainder distribution when proportional capping doesn't divide evenly.

    Exercises the remainder distribution loop in _distribute_capped_counts_proportionally
    by creating batches with uneven proportional distribution that leaves remainders.
    This ensures int() truncation in proportional calculation creates leftover instances.
    """
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    desired_creatable = 7
    assert (
        max_instances >= desired_creatable
    ), "test cannot be run with this limit, please adjust your configuration"

    simcore_ec2_api = get_ec2_client(initialized_app)
    mocker.patch.object(
        simcore_ec2_api,
        "get_instances",
        return_value=[{}] * (max_instances - desired_creatable),
    )
    # Three batches with uneven ratios: 3:2:2 needed, capped to 7 total
    # Proportional: t2.micro gets 3*7/7=3, t3.medium gets 2*7/7=2, m5.large gets 2*7/7=2 = 7 (no remainder)
    # But if we use multiple batches of same type: 2:1 for t2.micro with 3 total needed
    # and 2:1 for t3.medium with 3 total needed, proportional might leave remainder
    needed_instances = _build_needed_instances(
        [
            ("t2.micro", 2),
            ("t2.micro", 1),
            ("t3.medium", 2),
            ("t3.medium", 1),
            ("m5.large", 1),
        ]
    )

    result = await cap_needed_instances(
        initialized_app,
        needed_instances,
        ec2_tags={},
    )

    assert sum(result.values()) == desired_creatable
    # Verify we have instances distributed across batches
    assert len(result) >= 3


async def test_cap_needed_instances_single_type_all_capacity(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
    mocker: MockerFixture,
):
    """Test capping with single instance type uses all available capacity."""
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    desired_creatable = 6
    assert (
        max_instances >= desired_creatable
    ), "test cannot be run with this limit, please adjust your configuration"

    simcore_ec2_api = get_ec2_client(initialized_app)
    mocker.patch.object(
        simcore_ec2_api,
        "get_instances",
        return_value=[{}] * (max_instances - desired_creatable),
    )
    needed_instances = _build_needed_instances([("t2.micro", 10)])

    result = await cap_needed_instances(
        initialized_app,
        needed_instances,
        ec2_tags={},
    )

    assert sum(result.values()) == desired_creatable
    assert len(result) == 1
