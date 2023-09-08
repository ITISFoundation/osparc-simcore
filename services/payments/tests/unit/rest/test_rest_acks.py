import httpx
from faker import Faker
from fastapi import status
from pydantic import HttpUrl


async def test_bearer_token(httpbin_base_url: HttpUrl, faker: Faker):
    bearer_token = faker.word()
    headers = {"Authorization": f"Bearer {bearer_token}"}

    async with httpx.AsyncClient(base_url=httpbin_base_url, headers=headers) as client:

        response = await client.get("/bearer")
        assert response.json() == {"authenticated": True, "token": bearer_token}


async def test_it(client: httpx.AsyncClient):

    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith("simcore_service_payments.api._health@")
