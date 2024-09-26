# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_agent.core.application import create_app


@pytest.fixture
async def initialized_app(mock_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    app: FastAPI = create_app()

    async with LifespanManager(app):
        yield app


@pytest.fixture
def test_client(initialized_app: FastAPI) -> TestClient:
    return TestClient(initialized_app)


def test_health_ok(test_client: TestClient):
    response = test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), str)
