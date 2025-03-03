import httpx
import pytest
from fastapi import FastAPI, status
from models_library.projects_nodes_io import LocationID
from models_library.users import UserID
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from simcore_service_storage.datcore_dsm import DatCoreDataManager

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.mark.parametrize("entrypoint", ["list_paths"])
@pytest.mark.parametrize(
    "location_id",
    [DatCoreDataManager.get_location_id()],
    ids=[DatCoreDataManager.get_location_name()],
    indirect=True,
)
async def test_entrypoint_without_api_tokens_return_401(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    entrypoint: str,
    user_id: UserID,
):
    url = url_from_operation_id(
        client, initialized_app, entrypoint, location_id=f"{location_id}"
    ).with_query(
        user_id=user_id,
    )
    response = await client.get(f"{url}")
    assert_status(
        response,
        status.HTTP_401_UNAUTHORIZED,
        None,
    )
