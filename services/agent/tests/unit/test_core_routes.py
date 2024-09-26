# pylint: disable=protected-access
# pylint: disable=redefined-outer-name


from fastapi import status
from fastapi.testclient import TestClient

pytest_simcore_core_services_selection = [
    "rabbit",
]


def test_health_ok(test_client: TestClient):
    response = test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), str)
