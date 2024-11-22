# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import httpx
from fastapi import status


async def test_healthcheck(
    configure_registry_access,
    client: httpx.AsyncClient,
    api_version_prefix: str,
):
    resp = await client.get(f"/{api_version_prefix}/")

    assert resp.is_success
    assert resp.status_code == status.HTTP_200_OK
    assert "simcore_service_director" in resp.text
