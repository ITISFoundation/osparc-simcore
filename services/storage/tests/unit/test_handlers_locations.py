# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import httpx
from fastapi import FastAPI, status
from models_library.users import UserID
from pytest_simcore.helpers.httpx_assert_checks import url_from_operation_id
from tests.helpers.utils import has_datcore_tokens

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_locations(
    initialized_app: FastAPI, client: httpx.AsyncClient, user_id: UserID
):
    url = url_from_operation_id(
        client, initialized_app, "list_storage_locations"
    ).with_query(user_id=user_id)
    resp = await client.get(f"{url}")

    payload = resp.json()
    assert resp.status_code == status.HTTP_200_OK, str(payload)

    data, error = tuple(payload.get(k) for k in ("data", "error"))

    _locs = 2 if has_datcore_tokens() else 1
    assert len(data) == _locs
    assert not error
