import pytest
from async_asgi_testclient import TestClient
from simcore_service_dynamic_sidecar.models import ApplicationHealth


@pytest.mark.asyncio
@pytest.mark.parametrize("is_healthy,status_code", [(True, 200), (False, 400)])
async def test_is_healthy(
    test_client: TestClient, is_healthy: bool, status_code: int
) -> None:
    test_client.application.state.application_health.is_healthy = is_healthy
    response = await test_client.get("/health")
    assert response.status_code == status_code, response
    assert response.json() == ApplicationHealth(is_healthy=is_healthy).dict()
