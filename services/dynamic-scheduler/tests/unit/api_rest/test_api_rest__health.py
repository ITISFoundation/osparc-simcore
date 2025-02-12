# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from datetime import datetime

import pytest
from fastapi import status
from httpx import AsyncClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.api.rest._health import HealthCheckError


class MockHealth:
    def __init__(self, is_ok: bool) -> None:
        self.healthy: bool = is_ok
        self.is_healthy: bool = is_ok


@pytest.fixture
def mock_rabbitmq_clients(
    mocker: MockerFixture,
    rabbit_client_ok: bool,
    rabbit_rpc_server_ok: bool,
) -> None:
    base_path = "simcore_service_dynamic_scheduler.api.rest._dependencies"

    mocker.patch(
        f"{base_path}.get_rabbitmq_client", return_value=MockHealth(rabbit_client_ok)
    )
    mocker.patch(
        f"{base_path}.get_rabbitmq_rpc_server",
        return_value=MockHealth(rabbit_rpc_server_ok),
    )


@pytest.fixture
def mock_redis_client(
    mocker: MockerFixture,
    redis_client_ok: bool,
) -> None:
    base_path = "simcore_service_dynamic_scheduler.api.rest._dependencies"
    mocker.patch(
        f"{base_path}.get_all_redis_clients",
        return_value={0: MockHealth(redis_client_ok)},
    )


@pytest.fixture
def mock_docker_api_proxy(mocker: MockerFixture, docker_api_proxy_ok: bool) -> None:
    base_path = "simcore_service_dynamic_scheduler.api.rest._health"
    mocker.patch(
        f"{base_path}.is_docker_api_proxy_ready", return_value=docker_api_proxy_ok
    )


@pytest.fixture
def app_environment(
    mock_docker_api_proxy: None,
    mock_rabbitmq_clients: None,
    mock_redis_client: None,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment


@pytest.mark.parametrize(
    "rabbit_client_ok, rabbit_rpc_server_ok, redis_client_ok,, docker_api_proxy_ok, is_ok",
    [
        pytest.param(True, True, True, True, True, id="ok"),
        pytest.param(False, True, True, True, False, id="rabbit_client_bad"),
        pytest.param(True, False, True, True, False, id="rabbit_rpc_server_bad"),
        pytest.param(True, True, False, True, False, id="redis_client_bad"),
        pytest.param(True, True, True, False, False, id="docker_api_proxy_bad"),
    ],
)
async def test_health(client: AsyncClient, is_ok: bool):
    if is_ok:
        response = await client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert datetime.fromisoformat(response.text.split("@")[1])
    else:
        with pytest.raises(HealthCheckError):
            await client.get("/health")
