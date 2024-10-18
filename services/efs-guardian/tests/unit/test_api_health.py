# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import httpx
import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from starlette import status

pytest_simcore_core_services_selection = []
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
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


async def test_healthcheck(
    client: httpx.AsyncClient,
):
    response = await client.get("/")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    assert "simcore_service_efs_guardian" in response.text
