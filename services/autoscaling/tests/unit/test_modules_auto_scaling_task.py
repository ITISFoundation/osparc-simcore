# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from unittest import mock

import pytest
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.core.settings import ApplicationSettings

_FAST_POLL_INTERVAL = 1


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # fast interval
    monkeypatch.setenv("AUTOSCALING_POLL_INTERVAL", f"{_FAST_POLL_INTERVAL}")
    app_environment["AUTOSCALING_POLL_INTERVAL"] = f"{_FAST_POLL_INTERVAL}"
    return app_environment


@pytest.fixture
def mock_background_task(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_task.auto_scale_cluster",
        autospec=True,
    )


async def test_auto_scaling_task_not_created_if_no_mode_defined(
    app_environment: EnvVarsDict,
    mock_background_task: mock.Mock,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_POLL_INTERVAL.total_seconds() == _FAST_POLL_INTERVAL
    assert not hasattr(initialized_app.state, "autoscaler_task")
    await asyncio.sleep(5 * _FAST_POLL_INTERVAL)
    mock_background_task.assert_not_called()


async def test_auto_scaling_task_created_and_deleted_with_dynamic_mode(
    enabled_dynamic_mode: EnvVarsDict,
    mock_background_task: mock.Mock,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_POLL_INTERVAL.total_seconds() == _FAST_POLL_INTERVAL
    assert hasattr(initialized_app.state, "autoscaler_task")
    await asyncio.sleep(5 * _FAST_POLL_INTERVAL)
    mock_background_task.assert_called()


async def test_auto_scaling_task_created_and_deleted_with_computational_mode(
    enabled_computational_mode: EnvVarsDict,
    mock_background_task: mock.Mock,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_POLL_INTERVAL.total_seconds() == _FAST_POLL_INTERVAL
    assert hasattr(initialized_app.state, "autoscaler_task")
    await asyncio.sleep(5 * _FAST_POLL_INTERVAL)
    mock_background_task.assert_called()
