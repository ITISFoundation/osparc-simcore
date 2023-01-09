# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime

import pytest
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.settings import ApplicationSettings


def test_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_ACCESS
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert settings.AUTOSCALING_NODES_MONITORING
    assert settings.AUTOSCALING_RABBITMQ
    assert settings.AUTOSCALING_REDIS


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
