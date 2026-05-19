# pylint: disable=protected-access
# pylint: disable=redefined-outer-name


from fastapi import status
from fastapi.testclient import TestClient
from models_library.api_schemas__common.health import HealthCheckGet
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG

pytest_simcore_core_services_selection = [
    "rabbit",
]


def test_health_ok(test_client: TestClient):
    response = test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert HealthCheckGet.model_validate(response.json())


def test_health_returns_503_when_rabbitmq_unhealthy(test_client: TestClient):
    test_client.app.state.rabbitmq_rpc_client._healthy_state = False  # noqa: SLF001

    response = test_client.get("/health")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.text == RABBITMQ_CLIENT_UNHEALTHY_MSG
