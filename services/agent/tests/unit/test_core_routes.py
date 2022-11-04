# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

from time import time
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
    assert response.json() == None


def test_health_fails_not_started(
    env: None, initialized_app: FastAPI, test_client: TestClient
):
    task_monitor: TaskMonitor = initialized_app.state.task_monitor
    # emulate monitor not being started
    task_monitor._was_started = False

    response = test_client.get("/health")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "unhealthy"}


def test_health_fails_hanging_tasks(
    env: None, initialized_app: FastAPI, test_client: TestClient
):
    task_monitor: TaskMonitor = initialized_app.state.task_monitor

    # emulate tasks hanging
    for task_data in task_monitor._to_start.values():
        task_data._start_time = time() - 1e6

    response = test_client.get("/health")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "unhealthy"}
