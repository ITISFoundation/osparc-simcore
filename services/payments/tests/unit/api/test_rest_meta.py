# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import httpx
import simcore_service_payments.api.rest._health as health_module
from fastapi import status
from simcore_service_payments._meta import API_VTAG
from simcore_service_payments.models.schemas.meta import Meta


async def test_healthcheck(
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    client: httpx.AsyncClient,
):
    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith(
        f"{health_module.__name__}@"
    ), f"got {response.text!r}"


async def test_meta(
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
):
    response = await client.get(f"/{API_VTAG}/meta", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    meta = Meta.parse_obj(response.json())

    response = await client.get(meta.docs_url)
    assert response.status_code == status.HTTP_200_OK
