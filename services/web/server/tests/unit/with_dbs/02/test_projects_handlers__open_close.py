# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-statements
# pylint:disable=too-many-arguments

import asyncio
import json
import time
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Iterator, Optional, Union
from unittest import mock
from unittest.mock import call

import pytest
import socketio
from aiohttp import ClientResponse, web
from aiohttp.test_utils import TestClient, TestServer
from faker import Faker
from models_library.projects_access import Owner
from models_library.projects_state import (
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import log_client_in
from pytest_simcore.helpers.utils_projects import assert_get_same_project
from pytest_simcore.helpers.utils_webserver_unit_with_db import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp.web_exceptions_extension import HTTPLocked
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.projects.project_models import ProjectDict
from simcore_service_webserver.socketio.events import SOCKET_IO_PROJECT_UPDATED_EVENT
from simcore_service_webserver.utils import to_datetime
from socketio.exceptions import ConnectionError as SocketConnectionError

API_VERSION = "v0"
RESOURCE_NAME = "projects"
API_PREFIX = "/" + API_VERSION


@pytest.fixture
def app_environment(
    app_environment: dict[str, str], monkeypatch: MonkeyPatch
) -> dict[str, str]:
    # disable the garbage collector
    monkeypatch.setenv("WEBSERVER_GARBAGE_COLLECTOR", "null")
    return app_environment | {"WEBSERVER_GARBAGE_COLLECTOR": "null"}


def assert_replaced(current_project, update_data):
    def _extract(dikt, keys):
        return {k: dikt[k] for k in keys}

    modified = [
        "lastChangeDate",
    ]
    keep = [k for k in update_data.keys() if k not in modified]

    assert _extract(current_project, keep) == _extract(update_data, keep)

    k = "lastChangeDate"
    assert to_datetime(update_data[k]) < to_datetime(current_project[k])


async def _list_projects(
    client,
    expected: type[web.HTTPException],
    query_parameters: Optional[dict] = None,
) -> list[dict[str, Any]]:
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    assert str(url) == API_PREFIX + "/projects"
    if query_parameters:
        url = url.with_query(**query_parameters)

    resp = await client.get(url)
    data, _ = await assert_status(resp, expected)
    return data


async def _replace_project(
    client, project_update: dict, expected: type[web.HTTPException]
) -> dict:
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(
        project_id=project_update["uuid"]
    )
    assert str(url) == f"{API_PREFIX}/projects/{project_update['uuid']}"
    resp = await client.put(url, json=project_update)
    data, error = await assert_status(resp, expected)
    if not error:
        assert_replaced(current_project=data, update_data=project_update)
    return data


async def _connect_websocket(
    socketio_client_factory: Callable,
    check_connection: bool,
    client,
    client_id: str,
    events: Optional[dict[str, Callable]] = None,
) -> Optional[socketio.AsyncClient]:
    try:
        sio = await socketio_client_factory(client_id, client)
        assert sio.sid
        if events:
            for event, handler in events.items():
                sio.on(event, handler=handler)
        return sio
    except SocketConnectionError:
        if check_connection:
            pytest.fail("socket io connection should not fail")


async def _open_project(
    client,
    client_id: str,
    project: dict,
    expected: Union[type[web.HTTPException], list[type[web.HTTPException]]],
) -> tuple[dict, dict]:
    url = client.app.router["open_project"].url_for(project_id=project["uuid"])
    resp = await client.post(url, json=client_id)

    if isinstance(expected, list):
        for e in expected:
            try:
                data, error = await assert_status(resp, e)
                return data, error
            except AssertionError:
                # re-raise if last item
                if e == expected[-1]:
                    raise
                continue
    else:
        data, error = await assert_status(resp, expected)
        return data, error

    raise AssertionError("could not open project")


async def _close_project(
    client, client_id: str, project: dict, expected: type[web.HTTPException]
):
    url = client.app.router["close_project"].url_for(project_id=project["uuid"])
    resp = await client.post(url, json=client_id)
    await assert_status(resp, expected)


async def _state_project(
    client,
    project: dict,
    expected: type[web.HTTPException],
    expected_project_state: ProjectState,
):
    url = client.app.router["get_project_state"].url_for(project_id=project["uuid"])
    resp = await client.get(url)
    data, error = await assert_status(resp, expected)
    if not error:
        # the project is locked
        received_state = ProjectState(**data)
        assert received_state == expected_project_state


async def _assert_project_state_updated(
    handler: mock.Mock,
    shared_project: dict,
    expected_project_state_updates: list[ProjectState],
) -> None:
    if not expected_project_state_updates:
        handler.assert_not_called()
    else:
        # wait for the calls
        now = time.monotonic()
        MAX_WAITING_TIME = 15
        while time.monotonic() - now < MAX_WAITING_TIME:
            await asyncio.sleep(1)
            if handler.call_count == len(expected_project_state_updates):
                break
        if time.monotonic() - now > MAX_WAITING_TIME:
            pytest.fail(
                f"waited more than {MAX_WAITING_TIME}s and got only {handler.call_count}/{len(expected_project_state_updates)} calls"
            )

        calls = [
            call(
                json.dumps(
                    {
                        "project_uuid": shared_project["uuid"],
                        "data": p_state.dict(by_alias=True, exclude_unset=True),
                    }
                )
            )
            for p_state in expected_project_state_updates
        ]
        handler.assert_has_calls(calls)
        handler.reset_mock()


async def _delete_project(client, project: dict) -> ClientResponse:
    url = client.app.router["delete_project"].url_for(project_id=project["uuid"])
    assert str(url) == f"{API_PREFIX}/projects/{project['uuid']}"
    resp = await client.delete(url)
    return resp


@pytest.mark.parametrize(*standard_role_response())
@pytest.mark.parametrize(
    "share_rights",
    [
        {"read": True, "write": True, "delete": True},
        {"read": True, "write": True, "delete": False},
        {"read": True, "write": False, "delete": False},
        {"read": False, "write": False, "delete": False},
    ],
)
async def test_share_project(
    client,
    logged_user: dict,
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    all_group: dict[str, str],
    user_role: UserRole,
    expected: ExpectedResponse,
    storage_subsystem_mock,
    mocked_director_v2_api: dict[str, mock.Mock],
    catalog_subsystem_mock,
    share_rights: dict,
    project_db_cleaner,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    # Use-case: the user shares some projects with a group

    # create a few projects
    new_project = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        project={"accessRights": {str(all_group["gid"]): share_rights}},
    )
    if new_project:
        assert new_project["accessRights"] == {
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True},
            str(all_group["gid"]): share_rights,
        }

        # user 1 can always get to his project
        await assert_get_same_project(client, new_project, expected.ok)

    # get another user logged in now
    user_2 = await log_client_in(
        client, {"role": user_role.name}, enable_check=user_role != UserRole.ANONYMOUS
    )
    if new_project:
        # user 2 can only get the project if user 2 has read access
        await assert_get_same_project(
            client,
            new_project,
            expected.ok if share_rights["read"] else expected.forbidden,
        )
        # user 2 can only list projects if user 2 has read access
        list_projects = await _list_projects(client, expected.ok)
        assert len(list_projects) == (1 if share_rights["read"] else 0)
        # user 2 can only update the project is user 2 has write access
        project_update = deepcopy(new_project)
        project_update["name"] = "my super name"
        await _replace_project(
            client,
            project_update,
            expected.ok if share_rights["write"] else expected.forbidden,
        )
        # user 2 can only delete projects if user 2 has delete access
        resp = await _delete_project(client, new_project)
        await assert_status(
            resp,
            expected_cls=expected.no_content
            if share_rights["delete"]
            else expected.forbidden,
        )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_open_project(
    client,
    logged_user,
    user_project,
    client_session_id_factory: Callable,
    expected,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
):
    # POST /v0/projects/{project_id}:open
    # open project
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_session_id_factory())
    await assert_status(resp, expected)
    if resp.status == web.HTTPOk.status_code:
        dynamic_services = {
            service_uuid: service
            for service_uuid, service in user_project["workbench"].items()
            if "/dynamic/" in service["key"]
        }
        calls = []
        request_scheme = resp.url.scheme
        request_dns = f"{resp.url.host}:{resp.url.port}"
        for service_uuid, service in dynamic_services.items():
            calls.append(
                call(
                    client.server.app,
                    project_id=user_project["uuid"],
                    service_key=service["key"],
                    service_uuid=service_uuid,
                    service_version=service["version"],
                    user_id=logged_user["id"],
                    request_scheme=request_scheme,
                    request_dns=request_dns,
                    service_resources=ServiceResourcesDictHelpers.create_jsonable(
                        mock_service_resources
                    ),
                )
            )
        mocked_director_v2_api["director_v2_api.run_dynamic_service"].assert_has_calls(
            calls
        )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_open_project_with_deprecated_services_ok_but_does_not_start_dynamic_services(
    client,
    logged_user,
    user_project,
    client_session_id_factory: Callable,
    expected,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
):
    mock_catalog_api["get_service"].return_value["deprecated"] = (
        datetime.utcnow() - timedelta(days=1)
    ).isoformat()
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_session_id_factory())
    await assert_status(resp, expected)
    mocked_director_v2_api["director_v2_api.run_dynamic_service"].assert_not_called()


@pytest.mark.parametrize(*standard_role_response())
async def test_close_project(
    client,
    logged_user,
    user_project,
    client_session_id_factory: Callable,
    expected,
    mocked_director_v2_api: dict[str, mock.Mock],
    fake_services,
):
    # POST /v0/projects/{project_id}:close
    fake_dynamic_services = fake_services(number_services=5)
    assert len(fake_dynamic_services) == 5
    mocked_director_v2_api[
        "director_v2_core_dynamic_services.get_dynamic_services"
    ].return_value = fake_dynamic_services

    # open project
    client_id = client_session_id_factory()
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_id)

    if resp.status == web.HTTPOk.status_code:
        mocked_director_v2_api["director_v2_api.get_dynamic_services"].assert_any_call(
            client.server.app, logged_user["id"], user_project["uuid"]
        )
        mocked_director_v2_api[
            "director_v2_core_dynamic_services.get_dynamic_services"
        ].reset_mock()

    # close project
    url = client.app.router["close_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_id)
    await assert_status(resp, expected.no_content)

    if resp.status == web.HTTPNoContent.status_code:
        # These checks are after a fire&forget, so we wait a moment
        await asyncio.sleep(2)

        calls = [
            call(
                client.server.app,
                user_id=logged_user["id"],
                project_id=user_project["uuid"],
            ),
        ]
        mocked_director_v2_api[
            "director_v2_core_dynamic_services.get_dynamic_services"
        ].assert_has_calls(calls)

        calls = [
            call(
                app=client.server.app,
                service_uuid=service["service_uuid"],
                save_state=True,
            )
            for service in fake_dynamic_services
        ]
        mocked_director_v2_api[
            "director_v2_core_dynamic_services.stop_dynamic_service"
        ].assert_has_calls(calls)

        # should not be callsed request_retrieve_dyn_service


@pytest.mark.parametrize(
    "user_role, expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_get_active_project(
    client,
    logged_user,
    user_project,
    client_session_id_factory: Callable,
    expected,
    socketio_client_factory: Callable,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
):
    # login with socket using client session id
    client_id1 = client_session_id_factory()
    sio = None
    try:
        sio = await socketio_client_factory(client_id1)
        assert sio.sid
    except SocketConnectionError:
        if expected == web.HTTPOk:
            pytest.fail("socket io connection should not fail")

    # get active projects -> empty
    get_active_projects_url = (
        client.app.router["get_active_project"]
        .url_for()
        .with_query(client_session_id=client_id1)
    )
    resp = await client.get(get_active_projects_url)
    data, error = await assert_status(resp, expected)
    if resp.status == web.HTTPOk.status_code:
        assert not data
        assert not error

    # open project
    open_project_url = client.app.router["open_project"].url_for(
        project_id=user_project["uuid"]
    )
    resp = await client.post(open_project_url, json=client_id1)
    await assert_status(resp, expected)

    resp = await client.get(get_active_projects_url)
    data, error = await assert_status(resp, expected)
    if resp.status == web.HTTPOk.status_code:
        assert not error
        assert ProjectState(**data.pop("state")).locked.value
        assert data == user_project

    # login with socket using client session id2
    client_id2 = client_session_id_factory()
    try:
        sio = await socketio_client_factory(client_id2)
        assert sio.sid
    except SocketConnectionError:
        if expected == web.HTTPOk:
            pytest.fail("socket io connection should not fail")
    # get active projects -> empty
    get_active_projects_url = (
        client.app.router["get_active_project"]
        .url_for()
        .with_query(client_session_id=client_id2)
    )
    resp = await client.get(get_active_projects_url)
    data, error = await assert_status(resp, expected)
    if resp.status == web.HTTPOk.status_code:
        assert not data
        assert not error


@pytest.mark.parametrize(
    "user_role, expected_response_on_Create, expected_response_on_Get, expected_response_on_Delete",
    [
        (
            UserRole.USER,
            web.HTTPCreated,
            web.HTTPOk,
            web.HTTPNoContent,
        ),
        (
            UserRole.TESTER,
            web.HTTPCreated,
            web.HTTPOk,
            web.HTTPNoContent,
        ),
    ],
)
async def test_project_node_lifetime(
    client,
    logged_user,
    user_project,
    expected_response_on_Create,
    expected_response_on_Get,
    expected_response_on_Delete,
    mocked_director_v2_api: dict[str, mock.Mock],
    storage_subsystem_mock,
    mock_catalog_api: dict[str, mock.Mock],
    mocker,
    faker: Faker,
):

    mock_storage_api_delete_data_folders_of_project_node = mocker.patch(
        "simcore_service_webserver.projects.projects_handlers_crud.projects_api.storage_api.delete_data_folders_of_project_node",
        return_value="",
    )

    # create a new dynamic node...
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    body = {"service_key": "simcore/services/dynamic/key", "service_version": "1.3.4"}
    resp = await client.post(url, json=body)
    data, errors = await assert_status(resp, expected_response_on_Create)
    node_id = None
    if resp.status == web.HTTPCreated.status_code:
        mocked_director_v2_api[
            "director_v2_api.run_dynamic_service"
        ].assert_called_once()
        assert "node_id" in data
        node_id = data["node_id"]
    else:
        mocked_director_v2_api[
            "director_v2_api.run_dynamic_service"
        ].assert_not_called()

    # create a new NOT dynamic node...
    mocked_director_v2_api["director_v2_api.run_dynamic_service"].reset_mock()
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    body = {
        "service_key": "simcore/services/comp/key",
        "service_version": "1.3.4",
    }
    resp = await client.post(url, json=body)
    data, errors = await assert_status(resp, expected_response_on_Create)
    node_id_2 = None
    if resp.status == web.HTTPCreated.status_code:
        mocked_director_v2_api[
            "director_v2_api.run_dynamic_service"
        ].assert_not_called()
        assert "node_id" in data
        node_id_2 = data["node_id"]
    else:
        mocked_director_v2_api[
            "director_v2_api.run_dynamic_service"
        ].assert_not_called()

    # get the node state
    mocked_director_v2_api["director_v2_api.get_dynamic_services"].return_value = [
        {"service_uuid": node_id, "service_state": "running"}
    ]
    url = client.app.router["get_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    mocked_director_v2_api["director_v2_api.get_dynamic_service_state"].return_value = {
        "service_state": "running"
    }
    resp = await client.get(url)
    data, errors = await assert_status(resp, expected_response_on_Get)
    if resp.status == web.HTTPOk.status_code:
        assert "service_state" in data
        assert data["service_state"] == "running"

    # get the NOT dynamic node state
    mocked_director_v2_api["director_v2_api.get_dynamic_services"].return_value = []

    url = client.app.router["get_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id_2
    )
    mocked_director_v2_api["director_v2_api.get_dynamic_service_state"].return_value = {
        "service_state": "idle"
    }
    resp = await client.get(url)
    data, errors = await assert_status(resp, expected_response_on_Get)
    if resp.status == web.HTTPOk.status_code:
        assert "service_state" in data
        assert data["service_state"] == "idle"

    # delete the node
    mocked_director_v2_api["director_v2_api.get_dynamic_services"].return_value = [
        {"service_uuid": node_id}
    ]
    url = client.app.router["delete_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.delete(url)
    data, errors = await assert_status(resp, expected_response_on_Delete)
    if resp.status == web.HTTPNoContent.status_code:
        mocked_director_v2_api[
            "director_v2_api.stop_dynamic_service"
        ].assert_called_once()
        mock_storage_api_delete_data_folders_of_project_node.assert_called_once()
    else:
        mocked_director_v2_api[
            "director_v2_api.stop_dynamic_service"
        ].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_not_called()

    # delete the NOT dynamic node
    mocked_director_v2_api["director_v2_api.stop_dynamic_service"].reset_mock()
    mock_storage_api_delete_data_folders_of_project_node.reset_mock()
    # mock_director_api_get_running_services.return_value.set_result([{"service_uuid": node_id}])
    url = client.app.router["delete_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id_2
    )
    resp = await client.delete(url)
    data, errors = await assert_status(resp, expected_response_on_Delete)
    if resp.status == web.HTTPNoContent.status_code:
        mocked_director_v2_api[
            "director_v2_api.stop_dynamic_service"
        ].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_called_once()
    else:
        mocked_director_v2_api[
            "director_v2_api.stop_dynamic_service"
        ].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_not_called()


@pytest.fixture
def client_on_running_server_factory(
    client: TestClient, event_loop
) -> Iterator[Callable]:
    # Creates clients connected to the same server as the reference client
    #
    # Implemented as aihttp_client but creates a client using a running server,
    #  i.e. avoid client.start_server

    assert isinstance(client.server, TestServer)

    clients = []

    def go():
        cli = TestClient(client.server, loop=event_loop)
        assert client.server.started
        # AVOIDS client.start_server
        clients.append(cli)
        return cli

    yield go

    async def close_client_but_not_server(cli: TestClient):
        # pylint: disable=protected-access
        if not cli._closed:
            for resp in cli._responses:
                resp.close()
            for ws in cli._websockets:
                await ws.close()
            await cli._session.close()
            cli._closed = True

    async def finalize():
        while clients:
            await close_client_but_not_server(clients.pop())

    event_loop.run_until_complete(finalize())


@pytest.fixture
def clean_redis_table(redis_client):
    """this just ensures the redis table is cleaned up between test runs"""


@pytest.mark.parametrize(*standard_role_response())
async def test_open_shared_project_2_users_locked(
    client: TestClient,
    client_on_running_server_factory: Callable,
    logged_user: dict,
    shared_project: dict,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable,
    user_role: UserRole,
    expected: ExpectedResponse,
    mocker,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    clean_redis_table,
):
    # Use-case: user 1 opens a shared project, user 2 tries to open it as well
    mock_project_state_updated_handler = mocker.Mock()

    client_1 = client
    client_id1 = client_session_id_factory()
    client_2 = client_on_running_server_factory()
    client_id2 = client_session_id_factory()

    # 1. user 1 opens project
    sio_1 = await _connect_websocket(
        socketio_client_factory,
        user_role != UserRole.ANONYMOUS,
        client_1,
        client_id1,
        {SOCKET_IO_PROJECT_UPDATED_EVENT: mock_project_state_updated_handler},
    )
    # expected is that the project is closed and unlocked
    expected_project_state_client_1 = ProjectState(
        locked=ProjectLocked(value=False, status=ProjectStatus.CLOSED),
        state=ProjectRunningState(value=RunningState.NOT_STARTED),
    )
    for client_id in [client_id1, None]:
        await _state_project(
            client_1,
            shared_project,
            expected.ok if user_role != UserRole.GUEST else web.HTTPOk,
            expected_project_state_client_1,
        )
    await _open_project(
        client_1,
        client_id1,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else web.HTTPOk,
    )
    # now the expected result is that the project is locked and opened by client 1
    owner1 = Owner(
        user_id=logged_user["id"],
        first_name=(logged_user["name"].split(".") + [""])[0],
        last_name=(logged_user["name"].split(".") + [""])[1],
    )
    expected_project_state_client_1.locked.value = True
    expected_project_state_client_1.locked.status = ProjectStatus.OPENED
    expected_project_state_client_1.locked.owner = owner1
    # NOTE: there are 2 calls since we are part of the primary group and the all group
    await _assert_project_state_updated(
        mock_project_state_updated_handler,
        shared_project,
        [expected_project_state_client_1]
        * (0 if user_role == UserRole.ANONYMOUS else 2),
    )
    await _state_project(
        client_1,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else web.HTTPOk,
        expected_project_state_client_1,
    )

    # 2. create a separate client now and log in user2, try to open the same shared project
    user_2 = await log_client_in(
        client_2, {"role": user_role.name}, enable_check=user_role != UserRole.ANONYMOUS
    )
    sio_2 = await _connect_websocket(
        socketio_client_factory,
        user_role != UserRole.ANONYMOUS,
        client_2,
        client_id2,
        {SOCKET_IO_PROJECT_UPDATED_EVENT: mock_project_state_updated_handler},
    )
    await _open_project(
        client_2,
        client_id2,
        shared_project,
        expected.locked if user_role != UserRole.GUEST else HTTPLocked,
    )
    expected_project_state_client_2 = deepcopy(expected_project_state_client_1)
    expected_project_state_client_2.locked.status = ProjectStatus.OPENED

    await _state_project(
        client_2,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else web.HTTPOk,
        expected_project_state_client_2,
    )

    # 3. user 1 closes the project
    await _close_project(client_1, client_id1, shared_project, expected.no_content)
    if not any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST]):
        # Guests cannot close projects
        expected_project_state_client_1 = ProjectState(
            locked=ProjectLocked(value=False, status=ProjectStatus.CLOSED),
            state=ProjectRunningState(value=RunningState.NOT_STARTED),
        )

    # we should receive an event that the project lock state changed
    # NOTE: there are 2x3 calls since we are part of the primary group and the all group and user 2 is part of the all group
    # first CLOSING, then CLOSED
    await _assert_project_state_updated(
        mock_project_state_updated_handler,
        shared_project,
        [
            expected_project_state_client_1.copy(
                update={
                    "locked": ProjectLocked(
                        value=True, status=ProjectStatus.CLOSING, owner=owner1
                    )
                }
            )
        ]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 3
        )
        + [expected_project_state_client_1]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 3
        ),
    )
    await _state_project(
        client_1,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else web.HTTPOk,
        expected_project_state_client_1,
    )

    # 4. user 2 now should be able to open the project
    await _open_project(
        client_2,
        client_id2,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else HTTPLocked,
    )
    if not any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST]):
        expected_project_state_client_2.locked.value = True
        expected_project_state_client_2.locked.status = ProjectStatus.OPENED
        owner2 = Owner(
            user_id=user_2["id"],
            first_name=(user_2["name"].split(".") + [""])[0],
            last_name=(user_2["name"].split(".") + [""])[1],
        )
        expected_project_state_client_2.locked.owner = owner2
        expected_project_state_client_1.locked.value = True
        expected_project_state_client_1.locked.status = ProjectStatus.OPENED
        expected_project_state_client_1.locked.owner = owner2
    # NOTE: there are 3 calls since we are part of the primary group and the all group
    await _assert_project_state_updated(
        mock_project_state_updated_handler,
        shared_project,
        [expected_project_state_client_1]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 3
        ),
    )
    await _state_project(
        client_1,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else web.HTTPOk,
        expected_project_state_client_1,
    )


@pytest.mark.parametrize(*standard_role_response())
async def test_open_shared_project_at_same_time(
    client: TestClient,
    client_on_running_server_factory: Callable,
    logged_user: dict,
    shared_project: dict,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable,
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    clean_redis_table,
):
    NUMBER_OF_ADDITIONAL_CLIENTS = 20
    # log client 1
    client_1 = client
    client_id1 = client_session_id_factory()
    sio_1 = await _connect_websocket(
        socketio_client_factory,
        user_role != UserRole.ANONYMOUS,
        client_1,
        client_id1,
    )
    clients = [
        {"client": client_1, "user": logged_user, "client_id": client_id1, "sio": sio_1}
    ]
    # create other clients
    for i in range(NUMBER_OF_ADDITIONAL_CLIENTS):

        new_client = client_on_running_server_factory()
        user = await log_client_in(
            new_client,
            {"role": user_role.name},
            enable_check=user_role != UserRole.ANONYMOUS,
        )
        client_id = client_session_id_factory()
        sio = await _connect_websocket(
            socketio_client_factory,
            user_role != UserRole.ANONYMOUS,
            new_client,
            client_id,
        )
        clients.append(
            {"client": new_client, "user": user, "client_id": client_id, "sio": sio}
        )

    # try opening projects at same time (more or less)
    open_project_tasks = [
        _open_project(
            c["client"],
            c["client_id"],
            shared_project,
            [
                expected.ok if user_role != UserRole.GUEST else web.HTTPOk,
                expected.locked if user_role != UserRole.GUEST else HTTPLocked,
            ],
        )
        for c in clients
    ]
    results = await asyncio.gather(
        *open_project_tasks,
        return_exceptions=True,
    )

    # one should be opened, the other locked
    if user_role != UserRole.ANONYMOUS:
        num_assertions = 0
        for data, error in results:
            assert data or error
            if error:
                num_assertions += 1
            elif data:
                project_status = ProjectState(**data.pop("state"))
                assert data == shared_project
                assert project_status.locked.value
                assert project_status.locked.owner
                assert project_status.locked.owner.first_name in [
                    c["user"]["name"] for c in clients
                ]

        assert num_assertions == NUMBER_OF_ADDITIONAL_CLIENTS


@pytest.mark.parametrize(*standard_role_response())
async def test_opened_project_can_still_be_opened_after_refreshing_tab(
    client: TestClient,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    client_session_id_factory: Callable,
    socketio_client_factory: Callable,
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    clean_redis_table,
):
    """Simulating a refresh goes as follows:
    The user opens a project, then hit the F5 refresh page.
    The browser disconnects the websocket, reconnects but the
    client_session_id remains the same
    """

    client_session_id = client_session_id_factory()
    sio = await _connect_websocket(
        socketio_client_factory,
        user_role != UserRole.ANONYMOUS,
        client,
        client_session_id,
    )
    assert client.app
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(f"{url}", json=client_session_id)
    await assert_status(
        resp, expected.ok if user_role != UserRole.GUEST else web.HTTPOk
    )
    if resp.status != web.HTTPOk.status_code:
        return

    # the project is opened, now let's simulate a refresh
    assert sio
    await sio.disconnect()
    # give some time
    await asyncio.sleep(1)
    # re-connect using the same client session id
    sio2 = await _connect_websocket(
        socketio_client_factory,
        user_role != UserRole.ANONYMOUS,
        client,
        client_session_id,
    )
    assert sio2
    # re-open the project
    resp = await client.post(f"{url}", json=client_session_id)
    await assert_status(
        resp, expected.ok if user_role != UserRole.GUEST else web.HTTPOk
    )
