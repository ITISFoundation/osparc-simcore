# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime
import json

import pytest
from faker import Faker
from pydantic import ValidationError
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_autoscaling.core.settings import (
    ApplicationSettings,
    EC2InstancesSettings,
)
from types_aiobotocore_ec2.literals import InstanceTypeType


def test_ec2_instances_settings(app_environment: EnvVarsDict):
    settings = EC2InstancesSettings.create_from_envs()
    assert isinstance(settings.EC2_INSTANCES_ALLOWED_TYPES, dict)


@pytest.fixture
def instance_type_with_invalid_boot_script(
    mock_env_devel_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    ec2_instances: list[InstanceTypeType],
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {
                    ec2_type_name: {
                        "ami_id": faker.pystr(),
                        "custom_boot_scripts": ['ls"'],
                    }
                    for ec2_type_name in ec2_instances
                }
            ),
        },
    )


def test_ec2_instances_settings_with_invalid_custom_script_raises(
    app_environment: EnvVarsDict, instance_type_with_invalid_boot_script: EnvVarsDict
):
    with pytest.raises(ValidationError):
        EC2InstancesSettings.create_from_envs()


def test_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_ACCESS
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert settings.AUTOSCALING_NODES_MONITORING is None
    assert settings.AUTOSCALING_DASK is None
    assert settings.AUTOSCALING_RABBITMQ
    assert settings.AUTOSCALING_REDIS


def test_settings_dynamic_mode(enabled_dynamic_mode: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_ACCESS
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert settings.AUTOSCALING_NODES_MONITORING
    assert settings.AUTOSCALING_DASK is None
    assert settings.AUTOSCALING_RABBITMQ
    assert settings.AUTOSCALING_REDIS


def test_settings_computational_mode(enabled_computational_mode: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_ACCESS
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert settings.AUTOSCALING_NODES_MONITORING is None
    assert settings.AUTOSCALING_DASK
    assert settings.AUTOSCALING_RABBITMQ
    assert settings.AUTOSCALING_REDIS


def test_defining_both_computational_and_dynamic_modes_is_invalid_and_raises(
    enabled_dynamic_mode: EnvVarsDict, enabled_computational_mode: EnvVarsDict
):
    with pytest.raises(ValidationError):
        ApplicationSettings.create_from_envs()


def test_invalid_EC2_INSTANCES_TIME_BEFORE_TERMINATION(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("EC2_INSTANCES_TIME_BEFORE_TERMINATION", "1:05:00")
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
    assert (
        datetime.timedelta(minutes=59)
        == settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
    )

    monkeypatch.setenv("EC2_INSTANCES_TIME_BEFORE_TERMINATION", "-1:05:00")
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert (
        datetime.timedelta(minutes=0)
        == settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
    )


def test_EC2_INSTANCES_PRE_PULL_IMAGES(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert not settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_PRE_PULL_IMAGES

    # passing an invalid image tag name will fail
    monkeypatch.setenv(
        "EC2_INSTANCES_PRE_PULL_IMAGES", json.dumps(["io.simcore.some234.cool-"])
    )
    settings = ApplicationSettings.create_from_envs()
    assert not settings.AUTOSCALING_EC2_INSTANCES

    # passing a valid will pass
    monkeypatch.setenv(
        "EC2_INSTANCES_PRE_PULL_IMAGES",
        json.dumps(
            [
                "nginx:latest",
                "itisfoundation/my-very-nice-service:latest",
                "simcore/services/dynamic/another-nice-one:2.4.5",
                "asd",
            ]
        ),
    )
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert [
        "nginx:latest",
        "itisfoundation/my-very-nice-service:latest",
        "simcore/services/dynamic/another-nice-one:2.4.5",
        "asd",
    ] == settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_PRE_PULL_IMAGES
