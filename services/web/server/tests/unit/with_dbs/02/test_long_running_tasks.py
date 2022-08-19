# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient


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
