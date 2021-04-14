import pytest
from async_asgi_testclient import TestClient
from simcore_service_dynamic_sidecar.models import ApplicationHealth


@pytest.mark.asyncio
async def test_is_healthy(test_client: TestClient):
    response = await test_client.get("/health")
    assert response.status_code == 200, response
    assert response.json() == ApplicationHealth().dict()
