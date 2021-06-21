import httpx
import pytest
from starlette import status


@pytest.mark.asyncio
async def test_list_files_entrypoint(async_client: httpx.AsyncClient):
    response = await async_client.get("/files")
    assert response.status_code == status.HTTP_200_OK
