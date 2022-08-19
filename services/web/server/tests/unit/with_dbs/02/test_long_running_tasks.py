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


@pytest.mark.parametrize(
    "method,entrypoint,request_params",
    [
        ("GET", "list_tasks", {}),
        ("GET", "get_task_status", {"task_id": "some_fake_task_id"}),
        ("GET", "get_task_result", {"task_id": "some_fake_task_id"}),
        ("DELETE", "cancel_and_delete_task", {"task_id": "some_fake_task_id"}),
    ],
)
@pytest.mark.parametrize(*standard_role_response())
async def test_long_running_tasks_check_permissions(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: ExpectedResponse,
    method: str,
    entrypoint: str,
    request_params: dict[str, Any],
):
    assert client.app
    url = client.app.router[entrypoint].url_for(**request_params)
    resp = await client.request(method, f"{url}")
    await assert_status(resp, expected.ok)
