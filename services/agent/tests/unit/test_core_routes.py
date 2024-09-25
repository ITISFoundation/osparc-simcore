# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from simcore_service_agent.core.application import create_app


@pytest.fixture
async def initialized_app() -> AsyncIterator[FastAPI]:
    app: FastAPI = create_app()

    await app.router.startup()
    yield app
    await app.router.shutdown()


@pytest.fixture
def test_client(initialized_app: FastAPI) -> TestClient:
    return TestClient(initialized_app)


def test_health_ok(env: None, test_client: TestClient):
    response = test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), str)
