# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from _helpers import ExpectedResponse, standard_role_response
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_postgres_database.models.users import UserRole


@pytest.mark.parametrize(
    "method,entrypoint,request_params",
    [
        ("GET", "list_tasks", {}),
        ("GET", "get_task_status", {"task_id": "some_fake_task_id"}),
        ("GET", "get_task_result", {"task_id": "some_fake_task_id"}),
        ("DELETE", "cancel_and_delete_task", {"task_id": "some_fake_task_id"}),
    ],
)
async def test_long_running_tasks_access_restricted_to_logged_users(
    client: TestClient,
    method: str,
    entrypoint: str,
    request_params: dict[str, Any],
):
    assert client.app
    url = client.app.router[entrypoint].url_for(**request_params)
    resp = await client.request(method, f"{url}")
    assert resp.status == web.HTTPUnauthorized.status_code


def _tasks_role_responses() -> tuple[str, list[tuple[UserRole, ExpectedResponse]]]:
    all_roles = standard_role_response()
    return (
        all_roles[0],
        [
            (user_role, response)
            for user_role, response in all_roles[1]
            if user_role not in [UserRole.GUEST]  # NOTE: Guest is the same as user
        ],
    )


@pytest.mark.parametrize(*_tasks_role_responses())
async def test_listing_tasks_empty(
    client: TestClient,
    logged_user,
    expected,
):
    assert client.app
    list_task_url = client.app.router["list_tasks"].url_for()
    resp = await client.get(f"{list_task_url}")
    data, error = await assert_status(resp, expected.ok)
    if error:
        assert not data
        return
    assert data == []
