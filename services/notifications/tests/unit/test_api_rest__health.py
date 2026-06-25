# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from models_library.errors import (
    POSRGRES_DATABASE_UNHEALTHY_MSG,
    RABBITMQ_CLIENT_UNHEALTHY_MSG,
    REDIS_CLIENT_UNHEALTHY_MSG,
)
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_notifications.api.rest.dependencies import (
    get_postgres_liveness,
    get_rabbitmq_rpc_client,
    get_redis_client,
)


@pytest.fixture
def mock_lifespans(mocker: MockerFixture) -> None:
    mocker.patch("simcore_service_notifications.core.application.configure_postgres_database")

    for configure_fn in (
        "configure_postgres_liveness",
        "configure_smtp_config_check",
        "configure_rabbitmq_client",
        "configure_rpc_api",
        "configure_redis_client",
        "configure_task_manager",
    ):
        mocker.patch(f"simcore_service_notifications.core.application.{configure_fn}")


@pytest.fixture
def app_environment(
    mock_lifespans: None,
    monkeypatch: pytest.MonkeyPatch,
    mock_env_devel_environment: EnvVarsDict,
    mock_environment: EnvVarsDict,
    external_envfile_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **mock_environment,
            **mock_env_devel_environment,
            **external_envfile_dict,
            "NOTIFICATIONS_TRACING": "null",
            "NOTIFICATIONS_WORKER_MODE": "false",
        },
    )


def _get_mock(healthy: bool) -> Mock:
    mock = Mock()
    mock.is_healthy = healthy
    mock.healthy = healthy
    mock.is_responsive = healthy
    return mock


@pytest.fixture
def mock_services_health(
    mock_fastapi_app: FastAPI, rabbit_healthy: bool, postgres_healthy: bool, redis_healthy: bool
) -> Iterator[None]:
    mock_fastapi_app.dependency_overrides[get_rabbitmq_rpc_client] = lambda: _get_mock(rabbit_healthy)
    mock_fastapi_app.dependency_overrides[get_postgres_liveness] = lambda: _get_mock(postgres_healthy)
    mock_fastapi_app.dependency_overrides[get_redis_client] = lambda: _get_mock(redis_healthy)

    yield

    mock_fastapi_app.dependency_overrides.pop(get_rabbitmq_rpc_client, None)
    mock_fastapi_app.dependency_overrides.pop(get_postgres_liveness, None)
    mock_fastapi_app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.parametrize("rabbit_healthy", [True])
@pytest.mark.parametrize("postgres_healthy", [True])
@pytest.mark.parametrize("redis_healthy", [True])
def test_health_ok(mock_services_health: None, test_client: TestClient):
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    "rabbit_healthy, postgres_healthy, redis_healthy, expected_msg",
    [
        (True, True, False, REDIS_CLIENT_UNHEALTHY_MSG),
        (True, False, True, POSRGRES_DATABASE_UNHEALTHY_MSG),
        (False, True, True, RABBITMQ_CLIENT_UNHEALTHY_MSG),
    ],
)
def test_unhealthy_services(mock_services_health: None, test_client: TestClient, expected_msg: str):
    response = test_client.get("/")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert expected_msg in response.text
