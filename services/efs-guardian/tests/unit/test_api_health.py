# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from unittest.mock import Mock

import httpx
import pytest
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_efs_guardian.api.rest.health import HealthCheckError
from starlette import status

pytest_simcore_core_services_selection = []
pytest_simcore_ops_services_selection = []


@pytest.fixture
def mocked_get_rabbitmq_rpc_client(mocker: MockerFixture, is_healthy: bool) -> None:
    mock = Mock()
    mock.healthy = is_healthy
    for client in [
        "get_rabbitmq_client",
        "get_rabbitmq_rpc_client",
    ]:
        mocker.patch(f"simcore_service_efs_guardian.api.rest.health.{client}", return_value=mock)


@pytest.fixture
def app_environment(
    mocked_get_rabbitmq_rpc_client: None,
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    with_disabled_redis_and_background_tasks: None,
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
):
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
        },
    )


@pytest.mark.parametrize("is_healthy", [True, False])
async def test_healthcheck(client: httpx.AsyncClient, is_healthy: bool):
    if is_healthy:
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK
        assert "simcore_service_efs_guardian" in response.text
    else:
        with pytest.raises(HealthCheckError):
            await client.get("/")
