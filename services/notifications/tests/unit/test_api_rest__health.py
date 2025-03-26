# pylint: disable=protected-access
# pylint: disable=redefined-outer-name


from fastapi import status
from fastapi.testclient import TestClient
from models_library.api_schemas__common.health import HealthCheckGet

pytest_simcore_core_services_selection = [
    "rabbit",
]


def test_health_ok(test_client: TestClient):
    response = test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert HealthCheckGet.model_validate(response.json())
