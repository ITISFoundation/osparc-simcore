# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable, Iterator
from http import HTTPStatus
from typing import Any
from unittest import mock
from unittest.mock import MagicMock, call

import pytest
import redis.asyncio as aioredis
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_state import ProjectStatus
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_webserver_unit_with_db import (
    ExpectedResponse,
    MockedStorageSubsystem,
    standard_role_response,
)
from servicelib.aiohttp import status
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects import _crud_api_delete
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.projects_api import lock_with_notification
from socketio.exceptions import ConnectionError as SocketConnectionError


async def _request_delete_project(
    client: TestClient, project: ProjectDict, expected: HTTPStatus
) -> None:
    assert client.app

    url = client.app.router["delete_project"].url_for(project_id=project["uuid"])
    assert url.path == f"/{api_version_prefix}/projects/{project['uuid']}"

    resp = await client.delete(url.path)
    await assert_status(resp, expected)


@pytest.mark.parametrize(*standard_role_response())
async def test_delete_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    storage_subsystem_mock: MockedStorageSubsystem,
    mocked_director_v2_api: dict[str, MagicMock],
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    fake_services: Callable,
    assert_get_same_project_caller: Callable,
    mock_dynamic_scheduler_rabbitmq: None,
    mock_progress_bar: Any,
):
    assert client.app

    # DELETE /v0/projects/{project_id}
    fakes = fake_services(5)
    mocked_director_v2_api[
        "dynamic_scheduler.api.list_dynamic_services"
    ].return_value = fakes

    await _request_delete_project(client, user_project, expected.no_content)

    tasks = _crud_api_delete.get_scheduled_tasks(
        project_uuid=user_project["uuid"], user_id=logged_user["id"]
    )

    if expected.no_content == status.HTTP_204_NO_CONTENT:
        # Waits until deletion tasks are done
        assert (
            len(tasks) == 1
        ), f"Only one delete fire&forget task expected, got {tasks=}"
        # might have finished, and therefore there is no need to waith
        await tasks[0]

        mocked_director_v2_api[
            "dynamic_scheduler.api.list_dynamic_services"
        ].assert_called_once()

        expected_calls = [
            call(
                app=client.app,
                node_id=service["service_uuid"],
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=True,
                progress=mock_progress_bar.sub_progress(1),
            )
            for service in fakes
        ]
        mocked_director_v2_api[
            "dynamic_scheduler.api.stop_dynamic_service"
        ].assert_has_calls(expected_calls)

        await assert_get_same_project_caller(
            client, user_project, status.HTTP_404_NOT_FOUND
        )

    else:
        assert (
            len(tasks) == 0
        ), f"NO delete fire&forget tasks expected when response is {expected.no_content}, got {tasks=}"


@pytest.mark.parametrize(
    "user_role, expected_ok, expected_forbidden",
    [
        (
            UserRole.ANONYMOUS,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_401_UNAUTHORIZED,
        ),
        (UserRole.GUEST, status.HTTP_200_OK, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_200_OK, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_200_OK, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_delete_multiple_opened_project_forbidden(
    mocked_notifications_plugin: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocked_director_v2_api,
    create_dynamic_service_mock,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable,
    user_role: UserRole,
    expected_ok: HTTPStatus,
    expected_forbidden: HTTPStatus,
    redis_client: aioredis.Redis,
):
    assert client.app

    # service in project
    await create_dynamic_service_mock(logged_user["id"], user_project["uuid"])
    # open project in tab1
    client_session_id1 = client_session_id_factory()
    try:
        await socketio_client_factory(client_session_id1)
    except SocketConnectionError:
        if user_role != UserRole.ANONYMOUS:
            pytest.fail("socket io connection should not fail")

    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url.path, json=client_session_id1)
    data, error = await assert_status(resp, expected_ok)
    if data:
        mocked_notifications_plugin["subscribe"].assert_called_once_with(
            client.app, ProjectID(user_project["uuid"])
        )
    else:
        assert error
        mocked_notifications_plugin["subscribe"].assert_not_called()

    # delete project in tab2
    client_session_id2 = client_session_id_factory()
    try:
        await socketio_client_factory(client_session_id2)
    except SocketConnectionError:
        if user_role != UserRole.ANONYMOUS:
            pytest.fail("socket io connection should not fail")

    await _request_delete_project(client, user_project, expected_forbidden)


@pytest.fixture
def user_project_in_2_products(
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    postgres_db: sa.engine.Engine,
    faker: Faker,
) -> Iterator[ProjectDict]:
    fake_product_name = faker.name()
    with postgres_db.connect() as conn:
        conn.execute(products.insert().values(name=fake_product_name, host_regex=""))
        conn.execute(
            projects_to_products.insert().values(
                project_uuid=user_project["uuid"], product_name=fake_product_name
            )
        )
    yield user_project
    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(products.delete().where(products.c.name == fake_product_name))


@pytest.mark.parametrize(*standard_role_response())
async def test_delete_project_in_multiple_products_forbidden(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project_in_2_products: ProjectDict,
    expected: ExpectedResponse,
):
    assert client.app
    await _request_delete_project(client, user_project_in_2_products, expected.conflict)


@pytest.mark.parametrize(*standard_role_response())
async def test_delete_project_while_it_is_locked_raises_error(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
):
    assert client.app

    project_uuid = user_project["uuid"]
    user_id = logged_user["id"]
    async with lock_with_notification(
        app=client.app,
        project_uuid=project_uuid,
        status=ProjectStatus.CLOSING,
        user_id=user_id,
        user_name={"first_name": "test", "last_name": "test"},
        notify_users=False,
    ):
        await _request_delete_project(client, user_project, expected.conflict)
