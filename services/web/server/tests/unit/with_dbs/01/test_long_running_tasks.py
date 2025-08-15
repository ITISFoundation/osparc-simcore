# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-self-use
# pylint: disable=no-self-argument

from typing import Any
from unittest.mock import Mock

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole


@pytest.mark.parametrize(
    "method,entrypoint,request_params",
    [
        ("GET", "list_tasks", {}),
        ("GET", "get_task_status", {"task_id": "some_fake_task_id"}),
        ("GET", "get_task_result", {"task_id": "some_fake_task_id"}),
        ("DELETE", "remove_task", {"task_id": "some_fake_task_id"}),
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
    assert resp.status == status.HTTP_401_UNAUTHORIZED


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


@pytest.mark.parametrize("user_role", [UserRole.GUEST, UserRole.TESTER, UserRole.USER])
async def test_listing_tasks_with_list_inprocess_tasks_error(
    client: TestClient, logged_user, faker: Faker, mocker: MockerFixture
):
    assert client.app

    class _DummyTaskManager:
        async def list_tasks(self, *args, **kwargs):
            raise Exception  # pylint: disable=broad-exception-raised  # noqa: TRY002

    mock = Mock()
    mock.tasks_manager = _DummyTaskManager()

    mocker.patch(
        "servicelib.aiohttp.long_running_tasks._routes.get_long_running_manager",
        return_value=mock,
    )

    _async_jobs_listing_path = client.app.router["get_async_jobs"].url_for()
    resp = await client.request("GET", f"{_async_jobs_listing_path}")
    assert resp.status == status.HTTP_500_INTERNAL_SERVER_ERROR
