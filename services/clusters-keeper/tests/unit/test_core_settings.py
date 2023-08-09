# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime

import pytest
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_clusters_keeper.core.settings import ApplicationSettings


def test_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings.CLUSTERS_KEEPER_EC2_ACCESS
    assert settings.CLUSTERS_KEEPER_EC2_INSTANCES
    assert settings.CLUSTERS_KEEPER_RABBITMQ
    assert settings.CLUSTERS_KEEPER_REDIS


def test_invalid_EC2_INSTANCES_TIME_BEFORE_TERMINATION(  # noqa: N802
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("EC2_INSTANCES_TIME_BEFORE_TERMINATION", "1:05:00")
    settings = ApplicationSettings.create_from_envs()
    assert settings.CLUSTERS_KEEPER_EC2_INSTANCES
    assert settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
    assert (
        settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION  # noqa: SIM300
        == datetime.timedelta(minutes=59)
    )

    monkeypatch.setenv("EC2_INSTANCES_TIME_BEFORE_TERMINATION", "-1:05:00")
    settings = ApplicationSettings.create_from_envs()
    assert settings.CLUSTERS_KEEPER_EC2_INSTANCES
    assert (
        settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION  # noqa: SIM300
        == datetime.timedelta(minutes=0)
    )
