# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from unittest import mock

import pytest
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.settings import ApplicationSettings

_FAST_POLL_INTERVAL = 1


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    disabled_rabbitmq: None,
    mocked_aws_server_envs: None,
    mocked_redis_server: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # fast interval
    monkeypatch.setenv("AUTOSCALING_POLL_INTERVAL", f"{_FAST_POLL_INTERVAL}")
    app_environment["AUTOSCALING_POLL_INTERVAL"] = f"{_FAST_POLL_INTERVAL}"
    return app_environment


@pytest.fixture
def mock_background_task(mocker: MockerFixture) -> mock.Mock:
    mocked_task = mocker.patch(
        "simcore_service_autoscaling.auto_scaling_task.auto_scale_cluster",
        autospec=True,
    )
    return mocked_task


async def test_auto_scaling_task_created_and_deleted(
    app_environment: EnvVarsDict,
    mock_background_task: mock.Mock,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_POLL_INTERVAL.total_seconds() == _FAST_POLL_INTERVAL
    assert hasattr(initialized_app.state, "autoscaler_task")
    await asyncio.sleep(5 * _FAST_POLL_INTERVAL)
    mock_background_task.assert_called()
