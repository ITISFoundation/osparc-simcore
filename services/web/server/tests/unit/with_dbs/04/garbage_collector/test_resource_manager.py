# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from asyncio import Future
from collections.abc import Awaitable, Callable
from typing import Any
from unittest import mock

import pytest
import socketio
import socketio.exceptions
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.resource_manager.registry import (
    RedisResourceRegistry,
    UserSession,
    get_registry,
)
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
    logged_user: UserInfoDict,
    client: TestClient,
    socket_registry: RedisResourceRegistry,
    create_socketio_connection: Callable[
        [str | None, TestClient | None], Awaitable[tuple[socketio.AsyncClient, str]]
    ],
):
    sio, cur_client_session_id = await create_socketio_connection(None, client)
    sid = sio.get_sid()
    resource_key = UserSession(
        user_id=logged_user["id"], client_session_id=cur_client_session_id
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
    logged_user: UserInfoDict,
    client: TestClient,
    create_socketio_connection: Callable[
        [str | None, TestClient | None], Awaitable[tuple[socketio.AsyncClient, str]]
    ],
):
    NUMBER_OF_SOCKETS = 5
    resource_keys: list[UserSession] = []

    # connect multiple clients
    clients = []
    for socket_count in range(1, NUMBER_OF_SOCKETS + 1):
        sio, cur_client_session_id = await create_socketio_connection(None, client)
        resource_key = UserSession(
            user_id=logged_user["id"], client_session_id=cur_client_session_id
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
                    UserSession(user_id=logged_user["id"], client_session_id="*"),
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
    create_socketio_connection: Callable[
        [str | None, TestClient | None], Awaitable[tuple[socketio.AsyncClient, str]]
    ],
):
    sio, *_ = await create_socketio_connection(None, client)
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
    create_socketio_connection: Callable[
        [str | None, TestClient | None], Awaitable[tuple[socketio.AsyncClient, str]]
    ],
    expected,
    mocker: MockerFixture,
):
    assert client.app
    app = client.app
    socket_registry = get_registry(app)
    assert socket_registry

    # connect first socket
    sio, *_ = await create_socketio_connection(None, client)
    socket_logout_mock_callable = mocker.Mock()
    sio.on("logout", handler=socket_logout_mock_callable)

    # connect second socket
    sio2, cur_client_session_id2 = await create_socketio_connection(None, client)
    socket_logout_mock_callable2 = mocker.Mock()
    sio2.on("logout", handler=socket_logout_mock_callable2)

    # connect third socket
    sio3, *_ = await create_socketio_connection(None, client)
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
