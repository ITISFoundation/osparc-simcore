# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from unittest import mock

import pytest
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_clusters_keeper.core.settings import ApplicationSettings


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch, {"CLUSTERS_KEEPER_TASK_INTERVAL": "00:00:01"}
    )


@pytest.fixture
def mock_background_task(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_clusters_keeper.modules.clusters_management_task.check_clusters",
        autospec=True,
    )


async def test_clusters_management_task_created_and_deleted(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    mock_background_task: mock.Mock,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
):
    assert app_settings.CLUSTERS_KEEPER_TASK_INTERVAL.total_seconds() == 1
    assert hasattr(initialized_app.state, "clusters_cleaning_task")
    await asyncio.sleep(5)
    mock_background_task.assert_called()
