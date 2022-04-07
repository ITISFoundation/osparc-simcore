# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Callable, Dict, Type
from unittest.mock import MagicMock, call

import pytest
from _helpers import ExpectedResponse, MockedStorageSubsystem, standard_role_response
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.projects._delete import (
    get_delete_project_background_tasks,
)
from socketio.exceptions import ConnectionError as SocketConnectionError

# HELPERS -----------------------------------------------------------------------------------------


async def _request_delete_project(
    client, project: Dict, expected: Type[web.HTTPException]
) -> None:
    url = client.app.router["delete_project"].url_for(project_id=project["uuid"])
    assert str(url) == f"/{api_version_prefix}/projects/{project['uuid']}"

    resp = await client.delete(url)
    await assert_status(resp, expected)


# TESTS -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(*standard_role_response())
async def test_delete_project(
    client: TestClient,
    logged_user: Dict[str, Any],
    user_project: Dict[str, Any],
    expected: ExpectedResponse,
    storage_subsystem_mock: MockedStorageSubsystem,
    mocked_director_v2_api: Dict[str, MagicMock],
    catalog_subsystem_mock: Callable,
    fake_services: Callable,
    assert_get_same_project_caller: Callable,
):
    # DELETE /v0/projects/{project_id}
    fakes = fake_services(5)
    mocked_director_v2_api["director_v2_core.get_services"].return_value = fakes

    await _request_delete_project(client, user_project, expected.no_content)

    tasks = get_delete_project_background_tasks(
        project_uuid=user_project["uuid"], user_id=logged_user["id"]
    )

    if expected.no_content == web.HTTPNoContent:
        # Waits until deletion tasks are done
        assert len(tasks) <= 1, f"Only one delete f&f task expected, got {tasks=}"
        if tasks:
            # might have finished, and therefore there is no need to waith
            await tasks[0]

        mocked_director_v2_api["director_v2_core.get_services"].assert_called_once()

        expected_calls = [
            call(
                app=client.server.app,
                service_uuid=service["service_uuid"],
                save_state=True,
            )
            for service in fakes
        ]
        mocked_director_v2_api["director_v2_core.stop_service"].assert_has_calls(
            expected_calls
        )

        await assert_get_same_project_caller(client, user_project, web.HTTPNotFound)

    else:
        assert (
            len(tasks) == 0
        ), f"NO delete f&f tasks expected when response is {expected.no_content}, got {tasks=}"


@pytest.mark.parametrize(
    "user_role, expected_ok, expected_forbidden",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk, web.HTTPForbidden),
        (UserRole.USER, web.HTTPOk, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPOk, web.HTTPForbidden),
    ],
)
async def test_delete_multiple_opened_project_forbidden(
    client,
    logged_user,
    user_project,
    mocked_director_v2_api,
    create_dynamic_service_mock,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable,
    user_role,
    expected_ok,
    expected_forbidden,
):
    # service in project
    service = await create_dynamic_service_mock(logged_user["id"], user_project["uuid"])

    # open project in tab1
    client_session_id1 = client_session_id_factory()
    try:
        sio1 = await socketio_client_factory(client_session_id1)
    except SocketConnectionError:
        if user_role != UserRole.ANONYMOUS:
            pytest.fail("socket io connection should not fail")

    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_session_id1)
    await assert_status(resp, expected_ok)

    # delete project in tab2
    client_session_id2 = client_session_id_factory()
    try:
        sio2 = await socketio_client_factory(client_session_id2)
    except SocketConnectionError:
        if user_role != UserRole.ANONYMOUS:
            pytest.fail("socket io connection should not fail")

    await _request_delete_project(client, user_project, expected_forbidden)
