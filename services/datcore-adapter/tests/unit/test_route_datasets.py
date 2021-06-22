import httpx
import pytest
from starlette import status


@pytest.mark.asyncio
async def test_list_datasets_entrypoint(async_client: httpx.AsyncClient):
    response = await async_client.get(
        "v0/datasets",
        headers={
            "x-datcore-api-key": "4c4ac0e6-0d45-4d97-9778-ab71cf3d6cf4",
            "x-datcore-api-secret": "f10d4104-8c3e-44a1-87d5-6c6efcbe7da3",
        },
    )
    assert response.status_code == status.HTTP_200_OK
