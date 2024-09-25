# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from asyncio import Future
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import call

import pytest
import socketio
import socketio.exceptions
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import MockedStorageSubsystem
from pytest_simcore.helpers.webserver_projects import NewProject
from redis.asyncio import Redis
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.application_setup import is_setup_completed
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.director_v2.plugin import setup_director_v2
from simcore_service_webserver.garbage_collector import _core as gc_core
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.notifications.plugin import setup_notifications
from simcore_service_webserver.products.plugin import setup_products
from simcore_service_webserver.projects.exceptions import ProjectNotFoundError
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.projects.projects_api import (
    remove_project_dynamic_services,
    submit_delete_project_task,
)
from simcore_service_webserver.rabbitmq import setup_rabbitmq
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.resource_manager.registry import (
    RedisResourceRegistry,
    UserSessionDict,
    get_registry,
)
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.plugin import setup_session
from simcore_service_webserver.socketio.messages import SOCKET_IO_PROJECT_UPDATED_EVENT
from simcore_service_webserver.socketio.plugin import setup_socketio
from simcore_service_webserver.users.api import delete_user_without_projects
from simcore_service_webserver.users.exceptions import UserNotFoundError
from simcore_service_webserver.users.plugin import setup_users
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

SERVICE_DELETION_DELAY = 1


async def close_project(client, project_uuid: str, client_session_id: str) -> None:
    url = client.app.router["close_project"].url_for(project_id=project_uuid)
    resp = await client.post(url, json=client_session_id)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)


@pytest.fixture
async def open_project() -> AsyncIterator[Callable[..., Awaitable[None]]]:
    _opened_projects = []

    async def _open_project(client, project_uuid: str, client_session_id: str) -> None:
        url = client.app.router["open_project"].url_for(project_id=project_uuid)
        resp = await client.post(url, json=client_session_id)
        await assert_status(resp, status.HTTP_200_OK)
        _opened_projects.append((client, project_uuid, client_session_id))

    yield _open_project
    # cleanup, if we cannot close that is because the user_role might not allow it
    await asyncio.gather(
        *(
            close_project(client, project_uuid, client_session_id)
            for client, project_uuid, client_session_id in _opened_projects
        ),
        return_exceptions=True,
    )


@pytest.fixture
def app_environment(
    app_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    overrides = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_COMPUTATION": "1",
            "WEBSERVER_NOTIFICATIONS": "1",
        },
    )
    return app_environment | overrides


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_cfg: dict[str, Any],
    postgres_db: sa.engine.Engine,
    mock_orphaned_services,
    redis_client: Redis,
    monkeypatch_setenv_from_app_config: Callable,
    mock_dynamic_scheduler_rabbitmq: None,
) -> TestClient:
    cfg = deepcopy(app_cfg)
    assert cfg["rest"]["version"] == API_VTAG
    assert cfg["rest"]["enabled"]
    cfg["projects"]["enabled"] = True

    # sets TTL of a resource after logout
    cfg["resource_manager"][
        "resource_deletion_timeout_seconds"
    ] = SERVICE_DELETION_DELAY

    monkeypatch_setenv_from_app_config(cfg)
    app = create_safe_application(cfg)

    # activates only security+restAPI sub-modules

    assert setup_settings(app)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_socketio(app)
    setup_projects(app)
    setup_director_v2(app)
    assert setup_resource_manager(app)
    setup_rabbitmq(app)
    setup_notifications(app)
    setup_products(app)

    assert is_setup_completed("simcore_service_webserver.resource_manager", app)

    # NOTE: garbage_collector is disabled and instead explicitly called using
    # garbage_collectorgc_core.collect_garbage
    assert not is_setup_completed("simcore_service_webserver.garbage_collector", app)

    return event_loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
        )
    )


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


@pytest.fixture(autouse=True)
async def director_v2_mock(director_v2_service_mock) -> aioresponses:
    return director_v2_service_mock


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
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
):
    cur_client_session_id = client_session_id_factory()
    sio = await socketio_client_factory(cur_client_session_id)
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
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
):
    NUMBER_OF_SOCKETS = 5
    resource_keys: list[UserSessionDict] = []

    # connect multiple clients
    clients = []
    for socket_count in range(1, NUMBER_OF_SOCKETS + 1):
        cur_client_session_id = client_session_id_factory()
        sio = await socketio_client_factory(cur_client_session_id)
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

    for sio, resource_key in zip(clients, resource_keys):
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
    socketio_client_factory: Callable,
):
    sio = await socketio_client_factory()
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
    socketio_client_factory: Callable,
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


@pytest.mark.parametrize(
    "user_role, expected_save_state",
    [
        (UserRole.GUEST, False),
        (UserRole.USER, True),
        (UserRole.TESTER, True),
    ],
)
async def test_interactive_services_removed_after_logout(
    client: TestClient,
    logged_user: dict[str, Any],
    empty_user_project: dict[str, Any],
    mocked_director_v2_api: dict[str, mock.MagicMock],
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    client_session_id_factory: Callable[[], str],
    socketio_client_factory: Callable,
    storage_subsystem_mock: MockedStorageSubsystem,  # when guest user logs out garbage is collected
    director_v2_service_mock: aioresponses,
    expected_save_state: bool,
    open_project: Callable,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    assert client.app
    user_id = logged_user["id"]
    service = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project["uuid"]
    )
    # create websocket
    client_session_id1 = client_session_id_factory()
    sio = await socketio_client_factory(client_session_id1)
    assert sio
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # logout
    logout_url = client.app.router["auth_logout"].url_for()
    r = await client.post(
        f"{logout_url}", json={"client_session_id": client_session_id1}
    )
    assert r.url.path == logout_url.path
    await assert_status(r, status.HTTP_200_OK)

    # check result perfomed by background task
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(client.app)

    # assert dynamic service is removed *this is done in a fire/forget way so give a bit of leeway
    async for attempt in AsyncRetrying(**_TENACITY_ASSERT_RETRY):
        with attempt:
            print(
                f"--> Waiting for stop_dynamic_service with: {service.node_uuid}, {expected_save_state=}",
            )
            mocked_director_v2_api[
                "dynamic_scheduler.api.stop_dynamic_service"
            ].assert_awaited_with(
                app=client.app,
                dynamic_service_stop=DynamicServiceStop(
                    user_id=user_id,
                    project_id=service.project_id,
                    node_id=service.node_uuid,
                    simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                    save_state=expected_save_state,
                ),
                progress=mock.ANY,
            )


@pytest.mark.parametrize(
    "user_role, expected_save_state",
    [
        (UserRole.GUEST, False),
        (UserRole.USER, True),
        (UserRole.TESTER, True),
    ],
)
async def test_interactive_services_remain_after_websocket_reconnection_from_2_tabs(
    client: TestClient,
    logged_user: UserInfoDict,
    empty_user_project,
    mocked_director_v2_api,
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
    storage_subsystem_mock,  # when guest user logs out garbage is collected
    expected_save_state: bool,
    mocker: MockerFixture,
    open_project: Callable,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    assert client.app
    user_id = logged_user["id"]
    service = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project["uuid"]
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
    async for attempt in AsyncRetrying(
        **(_TENACITY_ASSERT_RETRY | {"wait": wait_fixed(0.1)})
    ):
        with attempt:
            socket_project_state_update_mock_callable.assert_called_with(
                jsonable_encoder(
                    {
                        "project_uuid": empty_user_project["uuid"],
                        "data": {
                            "locked": {
                                "value": False,
                                "owner": {
                                    "user_id": user_id,
                                    "first_name": logged_user.get("first_name", None),
                                    "last_name": logged_user.get("last_name", None),
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
    await gc_core.collect_garbage(client.app)

    # assert dynamic service is still around
    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # disconnect second websocket
    await sio2.disconnect()
    assert not sio2.sid
    # assert dynamic service is still around for now
    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # reconnect websocket
    sio2 = await socketio_client_factory(client_session_id2)
    # it should still be there even after waiting for auto deletion from garbage collector
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(client.app)

    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # now really disconnect
    await sio2.disconnect()
    await sio2.wait()
    assert not sio2.sid
    # run the garbage collector
    # event after waiting some time
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(client.app)

    await asyncio.sleep(0)
    # assert dynamic service is gone
    calls = [
        call(
            app=client.app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=service.project_id,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=expected_save_state,
                node_id=service.node_uuid,
            ),
            progress=mock.ANY,
        )
    ]
    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_has_calls(calls)


@pytest.fixture
async def mocked_notification_system(mocker):
    mocks = {}
    mocked_notification_system = mocker.patch(
        "simcore_service_webserver.projects.projects_api.retrieve_and_notify_project_locked_state",
        return_value=Future(),
    )
    mocked_notification_system.return_value.set_result("")
    mocks["mocked_notification_system"] = mocked_notification_system
    return mocks


@pytest.mark.parametrize(
    "user_role, expected_save_state",
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
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    mocked_notification_system,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
    asyncpg_storage_system_mock,
    storage_subsystem_mock,  # when guest user logs out garbage is collected
    expected_save_state: bool,
    open_project: Callable,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    user_id = logged_user["id"]
    # create server with delay set to DELAY
    service1 = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project["uuid"]
    )
    service2 = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project2["uuid"]
    )
    service3 = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project2["uuid"]
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
    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # wait the defined delay
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(client.app)
    # assert dynamic service 1 is removed
    calls = [
        call(
            app=client.app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=service1.project_id,
                node_id=service1.node_uuid,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=expected_save_state,
            ),
            progress=mock.ANY,
        )
    ]
    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_has_calls(calls)
    mocked_director_v2_api["dynamic_scheduler.api.stop_dynamic_service"].reset_mock()

    # disconnect websocket2
    await sio2.disconnect()
    assert not sio2.sid
    # assert dynamic services are still around
    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # wait the defined delay
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(client.app)
    # assert dynamic service 2,3 is removed
    calls = [
        call(
            app=client.server.app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=service2.project_id,
                node_id=service2.node_uuid,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=expected_save_state,
            ),
            progress=mock.ANY,
        ),
        call(
            app=client.server.app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=service3.project_id,
                node_id=service3.node_uuid,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=expected_save_state,
            ),
            progress=mock.ANY,
        ),
    ]
    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_has_calls(calls)
    mocked_director_v2_api["dynamic_scheduler.api.stop_dynamic_service"].reset_mock()


@pytest.mark.xfail(
    reason="it is currently not permitted to open the same project from 2 different tabs"
)
@pytest.mark.parametrize(
    "user_role, expected_save_state",
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
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    socketio_client_factory: Callable,
    client_session_id_factory: Callable[[], str],
    expected_save_state: bool,
    open_project: Callable,
):
    # create server with delay set to DELAY
    service = await create_dynamic_service_mock(
        user_id=logged_user["id"], project_id=empty_user_project["uuid"]
    )
    # open project in tab1
    client_session_id1 = client_session_id_factory()
    sio1 = await socketio_client_factory(client_session_id1)
    assert sio1
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # open project in tab2
    client_session_id2 = client_session_id_factory()
    sio2 = await socketio_client_factory(client_session_id2)
    assert sio2
    await open_project(client, empty_user_project["uuid"], client_session_id2)
    # close project in tab1
    await close_project(client, empty_user_project["uuid"], client_session_id1)
    # wait the defined delay
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(client.app)
    # assert dynamic service is still around
    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # close project in tab2
    await close_project(client, empty_user_project["uuid"], client_session_id2)
    # wait the defined delay
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(client.app)
    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_has_calls(
        [call(client.server.app, service.node_uuid, expected_save_state)]
    )


@pytest.mark.parametrize(
    "user_role, expect_call, expected_save_state",
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
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    client_session_id_factory: Callable[[], str],
    socketio_client_factory: Callable,
    # asyncpg_storage_system_mock,
    storage_subsystem_mock,  # when guest user logs out garbage is collected
    expect_call: bool,
    expected_save_state: bool,
    open_project: Callable,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    user_id = logged_user["id"]
    service = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project["uuid"]
    )
    # create websocket
    client_session_id1 = client_session_id_factory()
    sio: socketio.AsyncClient = await socketio_client_factory(client_session_id1)
    assert sio
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # logout
    logout_url = client.app.router["auth_logout"].url_for()
    r = await client.post(logout_url, json={"client_session_id": client_session_id1})
    assert r.url.path == logout_url.path
    await assert_status(r, status.HTTP_200_OK)

    # ensure sufficient time is wasted here
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(client.app)

    # assert dynamic service is removed
    calls = [
        call(
            app=client.server.app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=service.project_id,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=expected_save_state,
                node_id=service.node_uuid,
            ),
            progress=mock.ANY,
        )
    ]
    mocked_director_v2_api[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_has_calls(calls)

    # this call is done async, so wait a bit here to ensure it is correctly done
    async for attempt in AsyncRetrying(**_TENACITY_ASSERT_RETRY):
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
    with pytest.raises(ProjectNotFoundError):
        await remove_project_dynamic_services(
            user_id=user_id,
            project_uuid=empty_user_project["uuid"],
            app=client.app,
            user_name={"first_name": "my name is", "last_name": "pytest"},
            simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
        )
    # since the call to delete is happening as fire and forget task, let's wait until it is done
    async for attempt in AsyncRetrying(**_TENACITY_ASSERT_RETRY):
        with attempt:
            mock_storage_delete_data_folders.assert_called()
