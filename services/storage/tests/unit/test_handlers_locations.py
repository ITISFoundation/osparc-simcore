# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from models_library.users import UserID
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import status
from tests.helpers.utils import has_datcore_tokens

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_locations(client: httpx.AsyncClient, user_id: UserID):
    resp = await client.get(f"/v0/locations?user_id={user_id}")

    payload = await resp.json()
    assert resp.status == 200, str(payload)

    data, error = tuple(payload.get(k) for k in ("data", "error"))

    _locs = 2 if has_datcore_tokens() else 1
    assert len(data) == _locs
    assert not error


@pytest.mark.parametrize(
    "dry_run, fire_and_forget, expected_removed",
    [
        (None, None, []),
        (True, False, []),
        (True, True, []),
        (False, True, []),
        (False, False, []),
    ],
)
async def test_synchronise_meta_data_table(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: int,
    user_id: UserID,
    dry_run: bool | None,
    fire_and_forget: bool | None,
    expected_removed: list,
):
    query_params: dict[str, Any] = {"user_id": user_id}
    if dry_run:
        query_params["dry_run"] = f"{dry_run}"
    if fire_and_forget:
        query_params["fire_and_forget"] = f"{fire_and_forget}"
    url = (
        client.app.router["synchronise_meta_data_table"]
        .url_for(location_id=f"{location_id}")
        .with_query(**query_params)
    )
    resp = await client.post(
        f"{url}",
    )
    data, error = await assert_status(resp, status.HTTP_200_OK)
    assert not error
    assert data
    assert data["dry_run"] == (False if dry_run is None else dry_run)
    assert data["fire_and_forget"] == (
        False if fire_and_forget is None else fire_and_forget
    )
    assert data["removed"] == expected_removed
