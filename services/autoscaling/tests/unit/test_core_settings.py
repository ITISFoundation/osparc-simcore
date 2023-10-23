# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime
import json

import pytest
from pydantic import ValidationError
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.settings import ApplicationSettings


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
        settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        == datetime.timedelta(minutes=59)
    )

    monkeypatch.setenv("EC2_INSTANCES_TIME_BEFORE_TERMINATION", "-1:05:00")
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert (
        settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        == datetime.timedelta(minutes=0)
    )


def test_EC2_INSTANCES_PRE_PULL_IMAGES(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_PRE_PULL_IMAGES == []

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
    assert settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_PRE_PULL_IMAGES == [
        "nginx:latest",
        "itisfoundation/my-very-nice-service:latest",
        "simcore/services/dynamic/another-nice-one:2.4.5",
        "asd",
    ]
