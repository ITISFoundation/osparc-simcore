# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from asyncio import Future
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import socketio
import socketio.exceptions
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_projects import NewProject
from servicelib.aiohttp import status
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.projects._projects_service import (
    remove_project_dynamic_services,
    submit_delete_project_task,
)
from simcore_service_webserver.resource_manager.registry import (
    RedisResourceRegistry,
    UserSessionDict,
    get_registry,
)
from simcore_service_webserver.users.exceptions import UserNotFoundError
from simcore_service_webserver.users.users_service import delete_user_without_projects
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL


@pytest.fixture
def mock_storage_delete_data_folders(mocker: MockerFixture) -> mock.Mock:
    mocker.patch(
        "simcore_service_webserver.dynamic_scheduler.api.list_dynamic_services",
        autospec=True,
    )
    return mocker.patch(
        "simcore_service_webserver.projects._crud_api_delete.delete_data_folders_of_project",
        return_value=None,
    )


@pytest.fixture()
def socket_registry(client: TestClient) -> RedisResourceRegistry:
    app = client.server.app  # type: ignore
    return get_registry(app)


@pytest.fixture
async def empty_user_project(
    client,
    empty_project,
    logged_user,
    tests_data_dir: Path,
    osparc_product_name: str,
) -> AsyncIterator[dict[str, Any]]:
    project = empty_project()
    async with NewProject(
        project,
        client.app,
        user_id=logged_user["id"],
        tests_data_dir=tests_data_dir,
        product_name=osparc_product_name,
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def empty_user_project2(
    client,
    empty_project,
    logged_user,
    tests_data_dir: Path,
    osparc_product_name: str,
) -> AsyncIterator[dict[str, Any]]:
    project = empty_project()
    async with NewProject(
        project,
        client.app,
        user_id=logged_user["id"],
        tests_data_dir=tests_data_dir,
        product_name=osparc_product_name,
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


async def test_anonymous_websocket_connection(
    client_session_id_factory: Callable[[], str],
    socketio_url_factory: Callable,
    security_cookie_factory: Callable,
    mocker,
):
    sio = socketio.AsyncClient(
        ssl_verify=False
    )  # enginio 3.10.0 introduced ssl verification
    url = str(
        URL(socketio_url_factory()).with_query(
            {"client_session_id": client_session_id_factory()}
        )
    )
    headers = {}
    cookie = await security_cookie_factory()
    if cookie:
        # WARNING: engineio fails with empty cookies. Expects "key=value"
        headers.update({"Cookie": cookie})

    socket_connect_error = mocker.Mock()
    sio.on("connect_error", handler=socket_connect_error)
    with pytest.raises(socketio.exceptions.ConnectionError):
        await sio.connect(url, headers=headers)
    assert sio.sid is None
    socket_connect_error.assert_called_once()
    await sio.disconnect()
    assert not sio.sid


@pytest.mark.parametrize(
    "user_role",
    [
        # (UserRole.ANONYMOUS),
        (UserRole.GUEST),
        (UserRole.USER),
        (UserRole.TESTER),
    ],
)
async def test_websocket_resource_management(
    logged_user,
    socket_registry: RedisResourceRegistry,
    create_socketio_connection: Callable,
    client_session_id_factory: Callable[[], str],
):
    cur_client_session_id = client_session_id_factory()
    sio = await create_socketio_connection(cur_client_session_id)
    sid = sio.get_sid()
    resource_key = UserSessionDict(
        user_id=f"{logged_user['id']}", client_session_id=cur_client_session_id
    )

    assert await socket_registry.find_keys(("socket_id", sio.get_sid())) == [
        resource_key
    ]
    assert sio.get_sid() in await socket_registry.find_resources(
        resource_key, "socket_id"
    )
    assert len(await socket_registry.find_resources(resource_key, "socket_id")) == 1

    # NOTE: the socket.io client needs the websockets package in order to upgrade to websocket transport
    await sio.disconnect()
    await sio.wait()
    assert not sio.get_sid()

    async for attempt in AsyncRetrying(**_TENACITY_ASSERT_RETRY):
        with attempt:
            # now the entries should be removed
            assert not await socket_registry.find_keys(("socket_id", sio.get_sid()))
            assert sid not in await socket_registry.find_resources(
                resource_key, "socket_id"
            )
            assert not await socket_registry.find_resources(resource_key, "socket_id")


@pytest.mark.parametrize(
    "user_role",
    [
        # (UserRole.ANONYMOUS),
        (UserRole.GUEST),
        (UserRole.USER),
        (UserRole.TESTER),
    ],
)
async def test_websocket_multiple_connections(
    socket_registry: RedisResourceRegistry,
    logged_user,
    create_socketio_connection: Callable,
    client_session_id_factory: Callable[[], str],
):
    NUMBER_OF_SOCKETS = 5
    resource_keys: list[UserSessionDict] = []

    # connect multiple clients
    clients = []
    for socket_count in range(1, NUMBER_OF_SOCKETS + 1):
        cur_client_session_id = client_session_id_factory()
        sio = await create_socketio_connection(cur_client_session_id)
        resource_key = UserSessionDict(
            user_id=f"{logged_user['id']}", client_session_id=cur_client_session_id
        )
        assert await socket_registry.find_keys(("socket_id", sio.get_sid())) == [
            resource_key
        ]
        assert [sio.get_sid()] == await socket_registry.find_resources(
            resource_key, "socket_id"
        )
        assert (
            len(
                await socket_registry.find_resources(
                    {"user_id": str(logged_user["id"]), "client_session_id": "*"},
                    "socket_id",
                )
            )
            == socket_count
        )
        clients.append(sio)
        resource_keys.append(resource_key)

    for sio, resource_key in zip(clients, resource_keys, strict=True):
        sid = sio.get_sid()
        await sio.disconnect()
        await sio.wait()

        assert not sio.sid
        assert not await socket_registry.find_keys(("socket_id", sio.get_sid()))
        assert sid not in await socket_registry.find_resources(
            resource_key, "socket_id"
        )

    for resource_key in resource_keys:
        assert not await socket_registry.find_resources(resource_key, "socket_id")


_TENACITY_ASSERT_RETRY = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "wait": wait_fixed(0.5),
    "stop": stop_after_delay(30),
}


@pytest.mark.skip(
    reason="this test is here to show warnings when closing "
    "the socketio server and could be useful as a proof"
    "see https://github.com/miguelgrinberg/python-socketio/discussions/1092"
    "and simcore_service_webserver.socketio.server _socketio_server_cleanup_ctx"
)
@pytest.mark.parametrize(
    "user_role",
    [
        (UserRole.TESTER),
    ],
)
async def test_asyncio_task_pending_on_close(
    client: TestClient,
    logged_user: dict[str, Any],
    create_socketio_connection: Callable,
):
    sio = await create_socketio_connection()
    assert sio
    # this test generates warnings on its own


@pytest.mark.parametrize(
    "user_role,expected",
    [
        # (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_websocket_disconnected_after_logout(
    client: TestClient,
    logged_user: dict[str, Any],
    create_socketio_connection: Callable,
    client_session_id_factory: Callable[[], str],
    expected,
    mocker: MockerFixture,
):
    assert client.app
    app = client.app
    socket_registry = get_registry(app)
    assert socket_registry

    # connect first socket
    cur_client_session_id1 = client_session_id_factory()
    sio = await create_socketio_connection(cur_client_session_id1)
    socket_logout_mock_callable = mocker.Mock()
    sio.on("logout", handler=socket_logout_mock_callable)

    # connect second socket
    cur_client_session_id2 = client_session_id_factory()
    sio2 = await create_socketio_connection(cur_client_session_id2)
    socket_logout_mock_callable2 = mocker.Mock()
    sio2.on("logout", handler=socket_logout_mock_callable2)

    # connect third socket
    cur_client_session_id3 = client_session_id_factory()
    sio3 = await create_socketio_connection(cur_client_session_id3)
    socket_logout_mock_callable3 = mocker.Mock()
    sio3.on("logout", handler=socket_logout_mock_callable3)

    # logout client with socket 2
    logout_url = client.app.router["auth_logout"].url_for()
    r = await client.post(
        f"{logout_url}", json={"client_session_id": cur_client_session_id2}
    )
    assert r.url.path == logout_url.path
    await assert_status(r, expected)

    # the socket2 should be gone
    async for attempt in AsyncRetrying(**_TENACITY_ASSERT_RETRY):
        with attempt:
            assert not sio2.sid
            socket_logout_mock_callable2.assert_not_called()

            # the others should receive a logout message through their respective sockets
            socket_logout_mock_callable.assert_called_once()
            socket_logout_mock_callable2.assert_not_called()  # note 2 should be not called ever
            socket_logout_mock_callable3.assert_called_once()

            # first socket should be closed now
            assert not sio.sid
            # second socket also closed
            assert not sio3.sid


@pytest.fixture
async def mocked_notification_system(mocker):
    mocks = {}
    mocked_notification_system = mocker.patch(
        "simcore_service_webserver.projects._projects_service.retrieve_and_notify_project_locked_state",
        return_value=Future(),
    )
    mocked_notification_system.return_value.set_result("")
    mocks["mocked_notification_system"] = mocked_notification_system
    return mocks


@pytest.mark.parametrize("user_role", [UserRole.USER, UserRole.TESTER, UserRole.GUEST])
async def test_regression_removing_unexisting_user(
    director_v2_service_mock: aioresponses,
    client: TestClient,
    logged_user: dict[str, Any],
    empty_user_project: dict[str, Any],
    user_role: UserRole,
    mock_storage_delete_data_folders: mock.Mock,
) -> None:
    # regression test for https://github.com/ITISFoundation/osparc-simcore/issues/2504
    assert client.app
    # remove project
    user_id = logged_user["id"]
    delete_task = await submit_delete_project_task(
        app=client.app,
        project_uuid=empty_user_project["uuid"],
        user_id=user_id,
        simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    )
    await delete_task
    # remove user
    await delete_user_without_projects(app=client.app, user_id=user_id)

    with pytest.raises(UserNotFoundError):
        await remove_project_dynamic_services(
            user_id=user_id,
            project_uuid=empty_user_project["uuid"],
            app=client.app,
            simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
        )
    await remove_project_dynamic_services(
        user_id=user_id,
        project_uuid=empty_user_project["uuid"],
        app=client.app,
        simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    )
    # since the call to delete is happening as fire and forget task, let's wait until it is done
    async for attempt in AsyncRetrying(**_TENACITY_ASSERT_RETRY):
        with attempt:
            mock_storage_delete_data_folders.assert_called()
