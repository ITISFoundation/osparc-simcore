# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from fastapi import status
from httpx import AsyncClient
from models_library.app_diagnostics import AppStatusCheck
from pydantic import parse_obj_as
from respx import MockRouter
from simcore_service_api_server._meta import API_VERSION, API_VTAG


async def test_check_service_health(client: AsyncClient):
    response = await client.get(f"{API_VTAG}/")
    assert response.status_code == status.HTTP_200_OK
    assert "health" in response.text


async def test_get_service_state(
    client: AsyncClient,
    mocked_directorv2_service_api_base: MockRouter,
    mocked_webserver_service_api_base: MockRouter,
    mocked_catalog_service_api_base: MockRouter,
    mocked_storage_service_api_base: MockRouter,
):
    response = await client.get(f"{API_VTAG}/meta")
    assert response.status_code == status.HTTP_200_OK

    app_status_check = parse_obj_as(AppStatusCheck, response.json())
    print(app_status_check.json(indent=1))
    assert app_status_check.version == API_VERSION
