# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from httpx import AsyncClient
from simcore_service_comp_resource_manager._meta import api_version, api_vtag
from simcore_service_comp_resource_manager.models.schemas.meta import Meta

pytestmark = pytest.mark.asyncio


async def test_read_service_meta(client: AsyncClient):
    response = await client.get(f"{api_vtag}/meta")

    assert response.status_code == 200
    assert response.json()["version"] == api_version

    meta = Meta(**response.json())
    assert meta.version == api_version
