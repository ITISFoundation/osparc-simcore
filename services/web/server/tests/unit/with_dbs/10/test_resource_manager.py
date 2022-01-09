# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import asyncio
import json
import logging
from asyncio import Future
from copy import deepcopy
from typing import Any, Callable, Dict
from unittest import mock
from unittest.mock import call

import pytest
import socketio
import socketio.exceptions
import sqlalchemy as sa
import tenacity
from _helpers import MockedStorageSubsystem  # type: ignore
from aiohttp import web
from aiohttp.test_utils import TestClient
from aioredis import Redis
from aioresponses import aioresponses
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_projects import NewProject
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.director.module_setup import setup_director
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.login.module_setup import setup_login
from simcore_service_webserver.projects.module_setup import setup_projects
from simcore_service_webserver.projects.projects_api import (
    delete_project,
    remove_project_interactive_services,
)
from simcore_service_webserver.projects.projects_exceptions import ProjectNotFoundError
from simcore_service_webserver.resource_manager import config, garbage_collector
from simcore_service_webserver.resource_manager.module_setup import (
    setup_resource_manager,
)
from simcore_service_webserver.resource_manager.registry import (
    RedisResourceRegistry,
    get_registry,
)
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio.events import SOCKET_IO_PROJECT_UPDATED_EVENT
from simcore_service_webserver.socketio.module_setup import setup_socketio
from simcore_service_webserver.users import setup_users
from simcore_service_webserver.users_api import delete_user
from simcore_service_webserver.users_exceptions import UserNotFoundError
from six import reraise
from tenacity._asyncio import AsyncRetrying
from tenacity.after import after_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt, stop_after_delay
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)

API_VERSION = "v0"
GARBAGE_COLLECTOR_INTERVAL = 1
SERVICE_DELETION_DELAY = 1
CHECK_BACKGROUND_RETRY_POLICY = dict(
    stop=stop_after_attempt(2),
    wait=wait_fixed(SERVICE_DELETION_DELAY + GARBAGE_COLLECTOR_INTERVAL),
    retry=retry_if_exception_type(AssertionError),
    after=after_log(logger, logging.INFO),
    reraise=True,
)


@pytest.fixture
def mock_garbage_collector_task(mocker):
    """patch the setup of the garbage collector so we can call it manually"""
    mocker.patch(
        "simcore_service_webserver.resource_manager.module_setup.setup_garbage_collector",
        return_value="",
    )


@pytest.fixture
def mock_delete_data_folders_for_project(mocker):
    mocker.patch(
        "simcore_service_webserver.projects.projects_api.delete_data_folders_of_project",
        return_value=None,
    )


@pytest.fixture
def client(
    mock_garbage_collector_task,
    loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_cfg: Dict[str, Any],
    postgres_db: sa.engine.Engine,
    mock_orphaned_services,
    redis_client: Redis,
) -> TestClient:
    cfg = deepcopy(app_cfg)

    assert cfg["rest"]["version"] == API_VERSION
    assert cfg["rest"]["enabled"]
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True
    cfg[config.CONFIG_SECTION_NAME][
        "garbage_collection_interval_seconds"
    ] = GARBAGE_COLLECTOR_INTERVAL  # increase speed of garbage collection

    # fake config
    app = create_safe_application(cfg)

    # activates only security+restAPI sub-modules
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_socketio(app)
    setup_projects(app)
    setup_director(app)
    setup_director_v2(app)
    assert setup_resource_manager(app)

    return loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
        )
    )


@pytest.fixture()
def socket_registry(client: TestClient) -> RedisResourceRegistry:
    app = client.server.app  # type: ignore
    socket_registry = get_registry(app)
    return socket_registry


@pytest.fixture
async def empty_user_project(client, empty_project, logged_user) -> Dict[str, Any]:
    project = empty_project()
    async with NewProject(project, client.app, user_id=logged_user["id"]) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def empty_user_project2(client, empty_project, logged_user) -> Dict[str, Any]:
    project = empty_project()
    async with NewProject(project, client.app, user_id=logged_user["id"]) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture(autouse=True)
async def director_v2_mock(director_v2_service_mock) -> aioresponses:
    return director_v2_service_mock


# ------------------------ UTILS ----------------------------------
def set_service_deletion_delay(delay: int, app: web.Application):
    app[config.APP_CONFIG_KEY][config.CONFIG_SECTION_NAME][
        "resource_deletion_timeout_seconds"
    ] = delay


async def open_project(client, project_uuid: str, client_session_id: str) -> None:
    url = client.app.router["open_project"].url_for(project_id=project_uuid)
    resp = await client.post(url, json=client_session_id)
    await assert_status(resp, web.HTTPOk)


async def close_project(client, project_uuid: str, client_session_id: str) -> None:
    url = client.app.router["close_project"].url_for(project_id=project_uuid)
    resp = await client.post(url, json=client_session_id)
    await assert_status(resp, web.HTTPNoContent)


# ------------------------ TESTS -------------------------------
async def test_anonymous_websocket_connection(
    client_session_id_factory: Callable[[], str],
    socketio_url_factory: Callable,
    security_cookie_factory: Callable,
    mocker,
):
    from yarl import URL

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
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
):
    cur_client_session_id = client_session_id_factory()
    sio = await socketio_client_factory(cur_client_session_id)
    sid = sio.sid
    resource_key = {
        "user_id": str(logged_user["id"]),
        "client_session_id": cur_client_session_id,
    }
    # FIXME: this check fails with python-socketio>=5.0.0 (see requirements/_base.in)
    assert await socket_registry.find_keys(("socket_id", sio.sid)) == [resource_key]
    assert sio.sid in await socket_registry.find_resources(resource_key, "socket_id")
    assert len(await socket_registry.find_resources(resource_key, "socket_id")) == 1

    # NOTE: the socket.io client needs the websockets package in order to upgrade to websocket transport
    await sio.disconnect()
    assert not sio.sid
    # NOTE: let the disconnection propagate
    await asyncio.sleep(1)
    # now the entries should be removed
    assert not await socket_registry.find_keys(("socket_id", sio.sid))
    assert not sid in await socket_registry.find_resources(resource_key, "socket_id")
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
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
):
    NUMBER_OF_SOCKETS = 5
    resource_key = {}

    # connect multiple clients
    clients = []
    for socket_count in range(1, NUMBER_OF_SOCKETS + 1):
        cur_client_session_id = client_session_id_factory()
        sio = await socketio_client_factory(cur_client_session_id)
        resource_key = {
            "user_id": str(logged_user["id"]),
            "client_session_id": cur_client_session_id,
        }
        assert await socket_registry.find_keys(("socket_id", sio.sid)) == [resource_key]
        assert [sio.sid] == await socket_registry.find_resources(
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

    for sio in clients:
        sid = sio.sid
        await sio.disconnect()
        # need to attend the disconnect event to pass through the socketio internal queues
        await asyncio.sleep(
            0.1
        )  # must be >= 0.01 to work without issues, added some padding
        assert not sio.sid
        assert not await socket_registry.find_keys(("socket_id", sio.sid))
        assert not sid in await socket_registry.find_resources(
            resource_key, "socket_id"
        )

    assert not await socket_registry.find_resources(resource_key, "socket_id")


@pytest.mark.parametrize(
    "user_role,expected",
    [
        # (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_websocket_disconnected_after_logout(
    client: TestClient,
    logged_user: Dict[str, Any],
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
    expected,
    mocker: MockerFixture,
):
    app = client.server.app
    socket_registry = get_registry(app)

    # connect first socket
    cur_client_session_id1 = client_session_id_factory()
    sio = await socketio_client_factory(cur_client_session_id1)
    socket_logout_mock_callable = mocker.Mock()
    sio.on("logout", handler=socket_logout_mock_callable)

    # connect second socket
    cur_client_session_id2 = client_session_id_factory()
    sio2 = await socketio_client_factory(cur_client_session_id2)
    socket_logout_mock_callable2 = mocker.Mock()
    sio2.on("logout", handler=socket_logout_mock_callable2)

    # connect third socket
    cur_client_session_id3 = client_session_id_factory()
    sio3 = await socketio_client_factory(cur_client_session_id3)
    socket_logout_mock_callable3 = mocker.Mock()
    sio3.on("logout", handler=socket_logout_mock_callable3)

    # logout client with socket 2
    logout_url = client.app.router["auth_logout"].url_for()
    r = await client.post(
        f"{logout_url}", json={"client_session_id": cur_client_session_id2}
    )
    assert r.url_obj.path == logout_url.path
    await assert_status(r, expected)

    # the socket2 should be gone
    await asyncio.sleep(1)
    assert not sio2.sid
    socket_logout_mock_callable2.assert_not_called()

    # the others should receive a logout message through their respective sockets
    await asyncio.sleep(3)
    socket_logout_mock_callable.assert_called_once()
    socket_logout_mock_callable2.assert_not_called()  # note 2 should be not called ever
    socket_logout_mock_callable3.assert_called_once()

    await asyncio.sleep(3)
    # first socket should be closed now
    assert not sio.sid
    # second socket also closed
    assert not sio3.sid


@pytest.mark.parametrize(
    "user_role, exp_save_state",
    [
        (UserRole.GUEST, False),
        (UserRole.USER, True),
        (UserRole.TESTER, True),
    ],
)
async def test_interactive_services_removed_after_logout(
    client: TestClient,
    logged_user: Dict[str, Any],
    empty_user_project: Dict[str, Any],
    mocked_director_v2_api: Dict[str, mock.MagicMock],
    create_dynamic_service_mock,
    client_session_id_factory: Callable[[], str],
    socketio_client_factory: Callable,
    storage_subsystem_mock: MockedStorageSubsystem,  # when guest user logs out garbage is collected
    director_v2_service_mock: aioresponses,
    exp_save_state: bool,
):
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)
    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # create dynamic service - create_dynamic_service_mock fixture
    service = await create_dynamic_service_mock(
        logged_user["id"], empty_user_project["uuid"]
    )
    # create websocket
    client_session_id1 = client_session_id_factory()
    sio = await socketio_client_factory(client_session_id1)
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # logout
    logout_url = client.app.router["auth_logout"].url_for()
    r = await client.post(
        f"{logout_url}", json={"client_session_id": client_session_id1}
    )
    assert r.url_obj.path == logout_url.path
    await assert_status(r, web.HTTPOk)

    # check result perfomed by background task
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(client.app)

    # assert dynamic service is removed *this is done in a fire/forget way so give a bit of leeway
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(10), wait=wait_fixed(1)
    ):
        with attempt:
            mocked_director_v2_api["director_v2_core.stop_service"].assert_awaited_with(
                app=client.server.app,
                service_uuid=service["service_uuid"],
                save_state=exp_save_state,
            )


@pytest.mark.parametrize(
    "user_role, exp_save_state",
    [
        (UserRole.GUEST, False),
        (UserRole.USER, True),
        (UserRole.TESTER, True),
    ],
)
async def test_interactive_services_remain_after_websocket_reconnection_from_2_tabs(
    client,
    logged_user,
    empty_user_project,
    mocked_director_v2_api,
    create_dynamic_service_mock,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
    storage_subsystem_mock,  # when guest user logs out garbage is collected
    exp_save_state: bool,
    mocker: MockerFixture,
):
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)

    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # create dynamic service - create_dynamic_service_mock fixture
    service = await create_dynamic_service_mock(
        logged_user["id"], empty_user_project["uuid"]
    )
    # create first websocket
    client_session_id1 = client_session_id_factory()
    sio = await socketio_client_factory(client_session_id1)
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], client_session_id1)

    # create second websocket
    client_session_id2 = client_session_id_factory()
    sio2 = await socketio_client_factory(client_session_id2)
    assert sio.sid != sio2.sid
    socket_project_state_update_mock_callable = mocker.Mock()
    sio2.on(
        SOCKET_IO_PROJECT_UPDATED_EVENT,
        handler=socket_project_state_update_mock_callable,
    )
    # disconnect first websocket
    # NOTE: since the service deletion delay is set to 1 second for the test, we should not sleep as long here, or the user will be deleted
    # We have no mock-up for the heatbeat...
    await sio.disconnect()
    assert not sio.sid
    await asyncio.sleep(0.5)  # let the thread call the method
    socket_project_state_update_mock_callable.assert_called_with(
        json.dumps(
            {
                "project_uuid": empty_user_project["uuid"],
                "data": {
                    "locked": {
                        "value": False,
                        "owner": {
                            "user_id": logged_user["id"],
                            "first_name": logged_user["name"],
                            "last_name": "",
                        },
                        "status": "OPENED",
                    },
                    "state": {"value": "NOT_STARTED"},
                },
            }
        )
    )
    # open project in second client
    await open_project(client, empty_user_project["uuid"], client_session_id2)
    # ensure sufficient time is wasted here
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(client.app)
    # assert dynamic service is still around
    mocked_director_v2_api["director_v2_api.stop_service"].assert_not_called()
    # disconnect second websocket
    await sio2.disconnect()
    assert not sio2.sid
    # assert dynamic service is still around for now
    mocked_director_v2_api["director_v2_api.stop_service"].assert_not_called()
    # reconnect websocket
    sio2 = await socketio_client_factory(client_session_id2)
    # it should still be there even after waiting for auto deletion from garbage collector
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(client.app)
    mocked_director_v2_api["director_v2_api.stop_service"].assert_not_called()
    # now really disconnect
    await sio2.disconnect()
    assert not sio2.sid
    # run the garbage collector
    # event after waiting some time
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(client.app)
    await asyncio.sleep(1)
    # assert dynamic service is gone
    calls = [
        call(
            app=client.server.app,
            save_state=exp_save_state,
            service_uuid=service["service_uuid"],
        )
    ]
    mocked_director_v2_api["director_v2_core.stop_service"].assert_has_calls(calls)


@pytest.fixture
async def mocked_notification_system(mocker):
    mocks = {}
    mocked_notification_system = mocker.patch(
        "simcore_service_webserver.projects.projects_api.retrieve_and_notify_project_locked_state",
        return_value=Future(),
    )
    mocked_notification_system.return_value.set_result("")
    mocks["mocked_notification_system"] = mocked_notification_system
    yield mocks


@pytest.mark.parametrize(
    "user_role, exp_save_state",
    [
        (UserRole.GUEST, False),
        (UserRole.USER, True),
        (UserRole.TESTER, True),
    ],
)
async def test_interactive_services_removed_per_project(
    client,
    logged_user,
    empty_user_project,
    empty_user_project2,
    mocked_director_v2_api,
    create_dynamic_service_mock,
    mocked_notification_system,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
    asyncpg_storage_system_mock,
    storage_subsystem_mock,  # when guest user logs out garbage is collected
    exp_save_state: bool,
):
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)
    # create server with delay set to DELAY
    # login - logged_user fixture
    # create empty study1 in project1 - empty_user_project fixture
    # create empty study2 in project2- empty_user_project2 fixture
    # service1 in project1 = await create_dynamic_service_mock(logged_user["id"], empty_user_project["uuid"])
    # service2 in project2 = await create_dynamic_service_mock(logged_user["id"], empty_user_project["uuid"])
    # service3 in project2 = await create_dynamic_service_mock(logged_user["id"], empty_user_project["uuid"])
    service = await create_dynamic_service_mock(
        logged_user["id"], empty_user_project["uuid"]
    )
    service2 = await create_dynamic_service_mock(
        logged_user["id"], empty_user_project2["uuid"]
    )
    service3 = await create_dynamic_service_mock(
        logged_user["id"], empty_user_project2["uuid"]
    )
    # create websocket1 from tab1
    client_session_id1 = client_session_id_factory()
    sio1 = await socketio_client_factory(client_session_id1)
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # create websocket2 from tab2
    client_session_id2 = client_session_id_factory()
    sio2 = await socketio_client_factory(client_session_id2)
    await open_project(client, empty_user_project2["uuid"], client_session_id2)
    # disconnect websocket1
    await sio1.disconnect()
    assert not sio1.sid
    # assert dynamic service is still around
    mocked_director_v2_api["director_v2_api.stop_service"].assert_not_called()
    # wait the defined delay
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(client.app)
    # assert dynamic service 1 is removed
    calls = [
        call(
            app=client.server.app,
            save_state=exp_save_state,
            service_uuid=service["service_uuid"],
        )
    ]
    mocked_director_v2_api["director_v2_core.stop_service"].assert_has_calls(calls)
    mocked_director_v2_api["director_v2_core.stop_service"].reset_mock()

    # disconnect websocket2
    await sio2.disconnect()
    assert not sio2.sid
    # assert dynamic services are still around
    mocked_director_v2_api["director_v2_core.stop_service"].assert_not_called()
    # wait the defined delay
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(client.app)
    # assert dynamic service 2,3 is removed
    calls = [
        call(
            app=client.server.app,
            save_state=exp_save_state,
            service_uuid=service2["service_uuid"],
        ),
        call(
            app=client.server.app,
            save_state=exp_save_state,
            service_uuid=service3["service_uuid"],
        ),
    ]
    mocked_director_v2_api["director_v2_core.stop_service"].assert_has_calls(calls)
    mocked_director_v2_api["director_v2_core.stop_service"].reset_mock()


@pytest.mark.xfail(
    reason="it is currently not permitted to open the same project from 2 different tabs"
)
@pytest.mark.parametrize(
    "user_role, exp_save_state",
    [
        # (UserRole.ANONYMOUS),
        # (UserRole.GUEST),
        (UserRole.USER, True),
        (UserRole.TESTER, True),
    ],
)
async def test_services_remain_after_closing_one_out_of_two_tabs(
    client,
    logged_user,
    empty_user_project,
    empty_user_project2,
    mocked_director_v2_api,
    create_dynamic_service_mock,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
    exp_save_state: bool,
):
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)
    # create server with delay set to DELAY
    # login - logged_user fixture
    # create empty study in project - empty_user_project fixture
    # service in project = await create_dynamic_service_mock(logged_user["id"], empty_user_project["uuid"])
    service = await create_dynamic_service_mock(
        logged_user["id"], empty_user_project["uuid"]
    )
    # open project in tab1
    client_session_id1 = client_session_id_factory()
    sio1 = await socketio_client_factory(client_session_id1)
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # open project in tab2
    client_session_id2 = client_session_id_factory()
    sio2 = await socketio_client_factory(client_session_id2)
    await open_project(client, empty_user_project["uuid"], client_session_id2)
    # close project in tab1
    await close_project(client, empty_user_project["uuid"], client_session_id1)
    # wait the defined delay
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(client.app)
    # assert dynamic service is still around
    mocked_director_v2_api["director_v2_api.stop_service"].assert_not_called()
    # close project in tab2
    await close_project(client, empty_user_project["uuid"], client_session_id2)
    # wait the defined delay
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(client.app)
    mocked_director_v2_api["director_v2_api.stop_service"].assert_has_calls(
        [call(client.server.app, service["service_uuid"], exp_save_state)]
    )


@pytest.mark.parametrize(
    "user_role, expect_call, exp_save_state",
    [
        (UserRole.USER, False, True),
        (UserRole.TESTER, False, True),
        (UserRole.GUEST, True, False),
    ],
)
async def test_websocket_disconnected_remove_or_maintain_files_based_on_role(
    client,
    logged_user,
    empty_user_project,
    mocked_director_v2_api,
    create_dynamic_service_mock,
    client_session_id_factory: Callable[[], str],
    socketio_client_factory: Callable,
    # asyncpg_storage_system_mock,
    storage_subsystem_mock,  # when guest user logs out garbage is collected
    expect_call: bool,
    exp_save_state: bool,
):
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)
    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # create dynamic service - create_dynamic_service_mock fixture
    service = await create_dynamic_service_mock(
        logged_user["id"], empty_user_project["uuid"]
    )
    # create websocket
    client_session_id1 = client_session_id_factory()
    sio: socketio.AsyncClient = await socketio_client_factory(client_session_id1)
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # logout
    logout_url = client.app.router["auth_logout"].url_for()
    r = await client.post(logout_url, json={"client_session_id": client_session_id1})
    assert r.url_obj.path == logout_url.path
    await assert_status(r, web.HTTPOk)

    # ensure sufficient time is wasted here
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(client.app)

    # assert dynamic service is removed
    calls = [
        call(
            app=client.server.app,
            save_state=exp_save_state,
            service_uuid=service["service_uuid"],
        )
    ]
    mocked_director_v2_api["director_v2_core.stop_service"].assert_has_calls(calls)

    # this call is done async, so wait a bit here to ensure it is correctly done
    async for attempt in AsyncRetrying(reraise=True, stop=stop_after_delay(10)):
        with attempt:
            if expect_call:
                # make sure `delete_project` is called
                storage_subsystem_mock[1].assert_called_once()
                # make sure `delete_user` is called
                # asyncpg_storage_system_mock.assert_called_once()
            else:
                # make sure `delete_project` not called
                storage_subsystem_mock[1].assert_not_called()
                # make sure `delete_user` not called
                # asyncpg_storage_system_mock.assert_not_called()


@pytest.mark.parametrize("user_role", [UserRole.USER, UserRole.TESTER, UserRole.GUEST])
async def test_regression_removing_unexisting_user(
    client,
    logged_user,
    empty_user_project,
    user_role,
    mock_delete_data_folders_for_project,
) -> None:
    # regression test for https://github.com/ITISFoundation/osparc-simcore/issues/2504

    # remove project
    await delete_project(
        app=client.server.app,
        project_uuid=empty_user_project["uuid"],
        user_id=logged_user["id"],
    )
    # remove user
    await delete_user(app=client.server.app, user_id=logged_user["id"])

    with pytest.raises(UserNotFoundError):
        await remove_project_interactive_services(
            user_id=logged_user["id"],
            project_uuid=empty_user_project["uuid"],
            app=client.server.app,
        )
    with pytest.raises(ProjectNotFoundError):
        await remove_project_interactive_services(
            user_id=logged_user["id"],
            project_uuid=empty_user_project["uuid"],
            app=client.server.app,
            user_name={"first_name": "my name is", "last_name": "pytest"},
        )
