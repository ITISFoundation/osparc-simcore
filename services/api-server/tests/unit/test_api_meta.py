# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from httpx import AsyncClient
from simcore_service_api_server._meta import API_VERSION, API_VTAG
from simcore_service_api_server.models.schemas.meta import Meta

pytestmark = pytest.mark.asyncio


async def test_read_service_meta(client: AsyncClient):
    response = await client.get(f"{API_VTAG}/meta")

    assert response.status_code == 200
    assert response.json()["version"] == API_VERSION

    meta = Meta(**response.json())
    assert meta.version == API_VERSION
