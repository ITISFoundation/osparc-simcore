# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

from typing import AsyncIterator

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from simcore_service_agent.core.application import create_app
from simcore_service_agent.modules.task_monitor import TaskMonitor


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
    assert response.json() == {"task_monitor": True}


def test_health_fails(env: None, initialized_app: FastAPI, test_client: TestClient):
    task_monitor: TaskMonitor = initialized_app.state.task_monitor
    task_monitor._running = False

    response = test_client.get("/health")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "unhealthy"}
