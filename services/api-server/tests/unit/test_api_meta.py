# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from httpx import AsyncClient
from models_library.api_schemas__common.meta import BaseMeta
from simcore_service_api_server._meta import API_VERSION, API_VTAG


async def test_read_service_meta(client: AsyncClient):
    response = await client.get(f"{API_VTAG}/meta")

    assert response.status_code == 200
    assert response.json()["version"] == API_VERSION

    meta = BaseMeta(**response.json())
    assert meta.version == API_VERSION
