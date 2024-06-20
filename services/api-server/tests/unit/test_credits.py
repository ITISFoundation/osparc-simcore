from fastapi import status
from httpx import AsyncClient
from simcore_service_api_server._meta import API_VTAG


async def test_get_credits_price(client: AsyncClient):
    response = await client.get(f"{API_VTAG}/credits/price")
    assert response.status_code == status.HTTP_200_OK
