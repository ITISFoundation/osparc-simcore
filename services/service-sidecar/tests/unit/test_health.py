import pytest
from httpx import AsyncClient
from simcore_service_service_sidecar.models import ApplicationHealth


@pytest.mark.asyncio
async def test_is_healthy(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == ApplicationHealth().dict()
