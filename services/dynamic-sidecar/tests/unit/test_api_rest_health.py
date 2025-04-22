# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from async_asgi_testclient import TestClient
from fastapi import status
from simcore_service_dynamic_sidecar.models.schemas.application_health import (
    ApplicationHealth,
)

pytest_simcore_core_services_selection = [
    "postgres",
]

pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_is_healthy(test_client: TestClient) -> None:
    test_client.application.state.application_health.is_healthy = True
    response = await test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK, response
    assert response.json() == ApplicationHealth(is_healthy=True).model_dump()


async def test_is_unhealthy(test_client: TestClient) -> None:
    test_client.application.state.application_health.is_healthy = False
    response = await test_client.get("/health")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response
    assert response.json() == {
        "detail": ApplicationHealth(is_healthy=False).model_dump()
    }


async def test_is_unhealthy_via_rabbitmq(test_client: TestClient) -> None:
    # pylint: disable=protected-access
    test_client.application.state.rabbitmq_client._healthy_state = False  # noqa: SLF001
    response = await test_client.get("/health")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response
    assert response.json() == {"detail": "RabbitMQ client is in a bad state!"}
