# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import httpx
from fastapi import FastAPI, status
from models_library.api_schemas_storage.storage_schemas import FileLocation
from models_library.users import UserID
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from simcore_service_storage.datcore_dsm import DatCoreDataManager
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_locations(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    fake_datcore_tokens: tuple[str, str],
):
    url = url_from_operation_id(
        client, initialized_app, "list_storage_locations"
    ).with_query(user_id=user_id)
    response = await client.get(f"{url}")
    data, _ = assert_status(response, status.HTTP_200_OK, list[FileLocation])
    assert data
    assert len(data) == 2
    assert data[0] == FileLocation(
        id=SimcoreS3DataManager.get_location_id(),
        name=SimcoreS3DataManager.get_location_name(),
    )
    assert data[1] == FileLocation(
        id=DatCoreDataManager.get_location_id(),
        name=DatCoreDataManager.get_location_name(),
    )


async def test_locations_without_tokens(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
):
    url = url_from_operation_id(
        client, initialized_app, "list_storage_locations"
    ).with_query(user_id=user_id)
    response = await client.get(f"{url}")
    data, _ = assert_status(response, status.HTTP_200_OK, list[FileLocation])
    assert data
    assert len(data) == 1
    assert data[0] == FileLocation(
        id=SimcoreS3DataManager.get_location_id(),
        name=SimcoreS3DataManager.get_location_name(),
    )
