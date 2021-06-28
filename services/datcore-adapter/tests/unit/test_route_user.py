# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import Any, Dict, Optional

import httpx
import pytest
from starlette import status


@pytest.mark.asyncio
async def test_users_profile_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_client_mock: Optional[Any],
    pennsieve_api_headers: Dict[str, str],
):
    response = await async_client.get(
        "v0/user/profile",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
