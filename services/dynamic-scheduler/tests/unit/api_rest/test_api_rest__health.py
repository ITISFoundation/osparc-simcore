# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from datetime import datetime

import pytest
from fastapi import status
from httpx import AsyncClient
from pytest_simcore.helpers.typing_env import EnvVarsDict


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None, app_environment: EnvVarsDict
) -> EnvVarsDict:
    return app_environment


async def test_health(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert datetime.fromisoformat(response.text.split("@")[1])
