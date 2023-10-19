# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from async_asgi_testclient import TestClient
from fastapi import status
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.health_check import HealthReport


@pytest.fixture
def test_client(test_client: TestClient) -> TestClient:
    return test_client


@pytest.fixture
def failing_health_report() -> HealthReport:
    return HealthReport(
        is_healthy=False, ok_checks=["mock_ok"], failing_checks=["mock_failing"]
    )


@pytest.fixture
def mock_health_as_unhealthy(
    mocker: MockerFixture, failing_health_report: HealthReport
) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.api.health.is_healthy",
        return_value=failing_health_report,
    )


async def test_is_healthy(test_client: TestClient) -> None:
    response = await test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK, response
    assert response.json() == {"is_healthy": True, "error_message": None}


async def test_is_unhealthy(
    test_client: TestClient, mock_health_as_unhealthy: None
) -> None:
    response = await test_client.get("/health")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response
    assert response.json() == {
        "detail": {
            "is_healthy": False,
            "error_message": "Registered health checks status: ok_checks=['mock_ok'] failing_checks=['mock_failing']",
        }
    }
