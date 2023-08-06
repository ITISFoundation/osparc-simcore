# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from unittest import mock

import pytest
import requests_mock
from fastapi import FastAPI
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings

_FAST_POLL_INTERVAL = 1


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # fast interval
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {"RESOURCE_USAGE_TRACKER_EVALUATION_INTERVAL_SEC": f"{_FAST_POLL_INTERVAL}"},
    )


@pytest.fixture
def mock_background_task(mocker: MockerFixture) -> mock.Mock:
    mocked_task = mocker.patch(
        "simcore_service_resource_usage_tracker.prometheus_containers.plugin.collect_container_resource_usage_task",
        autospec=True,
    )
    return mocked_task


@pytest.mark.skip(
    reason="This test is currently not needed, as setup_background_task is commented out in application.py"
)
async def test_resource_tracker_disabled_if_prometheus_disabled_task_created_and_deleted(
    app_environment: EnvVarsDict,
    disabled_database: None,
    disabled_prometheus: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    mock_background_task: mock.Mock,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
):
    assert (
        app_settings.RESOURCE_USAGE_TRACKER_EVALUATION_INTERVAL_SEC.total_seconds()
        == _FAST_POLL_INTERVAL
    )
    assert hasattr(initialized_app.state, "resource_tracker_task")
    assert initialized_app.state.resource_tracker_task is None
    await asyncio.sleep(5 * _FAST_POLL_INTERVAL)
    mock_background_task.assert_not_called()


@pytest.mark.skip(
    reason="This test is currently not needed, as setup_background_task is commented out in application.py"
)
async def test_resource_tracker_task_created_and_deleted(
    disabled_rabbitmq: None,
    disabled_database: None,
    app_environment: EnvVarsDict,
    mocked_prometheus: requests_mock.Mocker,
    mocked_redis_server: None,
    mock_background_task: mock.Mock,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
):
    assert (
        app_settings.RESOURCE_USAGE_TRACKER_EVALUATION_INTERVAL_SEC.total_seconds()
        == _FAST_POLL_INTERVAL
    )

    assert hasattr(initialized_app.state, "resource_tracker_task")
    # assert initialized_app.state.resource_tracker_task is not None
    await asyncio.sleep(5 * _FAST_POLL_INTERVAL)
    mock_background_task.assert_called()
