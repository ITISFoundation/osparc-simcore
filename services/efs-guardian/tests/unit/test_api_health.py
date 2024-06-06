# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import httpx
from starlette import status


async def test_healthcheck(client: httpx.AsyncClient):
    response = await client.get("/")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    assert "simcore_service_efs_guardian" in response.text
