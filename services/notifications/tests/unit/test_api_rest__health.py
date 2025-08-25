# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import pytest
from fastapi import status
from fastapi.testclient import TestClient
from models_library.api_schemas__common.health import HealthCheckGet
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG
from pytest_mock import MockerFixture
from simcore_service_notifications.api.rest._health import HealthCheckError

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]


def test_health_ok(test_client: TestClient):
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert HealthCheckGet.model_validate(response.json())


@pytest.fixture
def mock_rabbit_healthy(mocker: MockerFixture, test_client: TestClient) -> None:
    mocker.patch.object(
        test_client.app.state.rabbitmq_rpc_server, "_healthy_state", new=False
    )


def test_health_rabbit_unhealthy(mock_rabbit_healthy: None, test_client: TestClient):
    with pytest.raises(HealthCheckError) as exc:
        test_client.get("/")
    assert RABBITMQ_CLIENT_UNHEALTHY_MSG in f"{exc.value}"
