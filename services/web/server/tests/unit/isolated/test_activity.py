# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from aiohttp.client_exceptions import ClientConnectionError
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.activity.plugin import setup_activity
from simcore_service_webserver.application_settings import (
    PrometheusSettings,
    setup_settings,
)
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.session.plugin import setup_session


@pytest.fixture
def mocked_monitoring(mocker: MockerFixture, activity_data: dict[str, Any]) -> None:
    prometheus_data: dict[str, Any] = activity_data["prometheus"]

    cpu_ret = prometheus_data.get("cpu_return")
    mocker.patch(
        "simcore_service_webserver.activity._handlers.get_cpu_usage",
        return_value=cpu_ret,
    )

    mem_ret = prometheus_data.get("memory_return")
    mocker.patch(
        "simcore_service_webserver.activity._handlers.get_memory_usage",
        return_value=mem_ret,
    )

    labels_ret = prometheus_data.get("labels_return")
    mocker.patch(
        "simcore_service_webserver.activity._handlers.get_container_metric_for_labels",
        return_value=labels_ret,
    )


@pytest.fixture
def mocked_monitoring_down(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_webserver.activity._api.query_prometheus",
        side_effect=ClientConnectionError,
    )


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    envs = mock_env_devel_environment | setenvs_from_dict(
        monkeypatch,
        {
            "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED": "True",
            "LOGIN_REGISTRATION_INVITATION_REQUIRED": "False",
            "POSTGRES_DB": "simcoredb",
            "POSTGRES_HOST": "postgres",
            "POSTGRES_MAXSIZE": "10",
            "POSTGRES_MINSIZE": "10",
            "POSTGRES_MAX_POOLSIZE": "10",
            "POSTGRES_MAX_OVERFLOW": "20",
            "POSTGRES_PASSWORD": "simcore",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "simcore",
            "PROMETHEUS_PASSWORD": "fake",
            "PROMETHEUS_URL": "http://prometheus:9090",
            "PROMETHEUS_USERNAME": "fake",
            "PROMETHEUS_VTAG": "v1",
            "SESSION_SECRET_KEY": "REPLACE_ME_with_result__Fernet_generate_key=",
            "SMTP_HOST": "mail.foo.com",
            "SMTP_PORT": "25",
            "STORAGE_HOST": "storage",
            "STORAGE_PORT": "11111",
            "STORAGE_VTAG": "v0",
            "WEBSERVER_LOGIN": "null",
            "WEBSERVER_LOGLEVEL": "DEBUG",
            "WEBSERVER_PORT": "8080",
            "WEBSERVER_STUDIES_ACCESS_ENABLED": "True",
            "WEBSERVER_RPC_NAMESPACE": "null",
        },
    )

    monkeypatch.delenv("WEBSERVER_ACTIVITY")
    envs.pop("WEBSERVER_ACTIVITY")

    return envs


@pytest.fixture
async def client(
    aiohttp_client: Callable[..., Awaitable[TestClient]],
    mock_orphaned_services: MagicMock,
    app_environment: EnvVarsDict,
    mocked_db_setup_in_setup_security: MockType,
):
    # app_environment are in place
    assert {key: os.environ[key] for key in app_environment} == app_environment
    expected_activity_settings = PrometheusSettings.create_from_envs()

    app = create_safe_application()

    settings = setup_settings(app)
    assert expected_activity_settings == settings.WEBSERVER_ACTIVITY

    setup_session(app)
    setup_rest(app)
    assert mocked_db_setup_in_setup_security.called

    assert setup_activity(app)

    return await aiohttp_client(app)


async def test_has_login_required(client: TestClient):
    resp = await client.get("/v0/activity/status")
    await assert_status(resp, status.HTTP_401_UNAUTHORIZED)


async def test_monitoring_up(
    mocked_login_required: None, mocked_monitoring: None, client: TestClient
):
    RUNNING_NODE_ID = "894dd8d5-de3b-4767-950c-7c3ed8f51d8c"

    resp = await client.get("/v0/activity/status")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert RUNNING_NODE_ID in data, "Running node not present"

    prometheus = data.get(RUNNING_NODE_ID, {})

    assert "limits" in prometheus, "There is no limits key for executing node"
    assert "stats" in prometheus, "There is no stats key for executed node"

    limits = prometheus.get("limits", {})
    assert limits.get("cpus") == 4.0, "Incorrect value: Cpu limit"
    assert limits.get("mem") == 2048.0, "Incorrect value: Memory limit"

    stats = prometheus.get("stats", {})
    assert stats.get("cpuUsage") == 3.9952102200000006, "Incorrect value: Cpu usage"
    assert stats.get("memUsage") == 177.664, "Incorrect value: Memory usage"


async def test_monitoring_down(
    mocked_login_required: None, mocked_monitoring_down: None, client: TestClient
):
    resp = await client.get("/v0/activity/status")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)
