# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from async_asgi_testclient import TestClient
from fastapi import status
from simcore_service_dynamic_sidecar.models.schemas.application_health import (
    ApplicationHealth,
)


@pytest.fixture
def test_client(mock_node_ports_v2_ports: None, test_client: TestClient) -> TestClient:
    return test_client


async def test_is_healthy(test_client: TestClient) -> None:
    test_client.application.state.application_health.is_healthy = True
    response = await test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK, response
    assert response.json() == ApplicationHealth(is_healthy=True).dict()


async def test_is_unhealthy(test_client: TestClient) -> None:
    test_client.application.state.application_health.is_healthy = False
    response = await test_client.get("/health")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response
    assert response.json() == {"detail": ApplicationHealth(is_healthy=False).dict()}
