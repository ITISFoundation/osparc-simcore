# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import pytest
from fastapi import status
from httpx import AsyncClient
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler._meta import API_VTAG
from simcore_service_dynamic_scheduler.models.schemas.meta import Meta


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None,
    disable_redis_setup: None,
    disable_service_tracker_setup: None,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment


async def test_health(client: AsyncClient):
    response = await client.get(f"/{API_VTAG}/meta")
    assert response.status_code == status.HTTP_200_OK
    assert Meta.parse_raw(response.text)
