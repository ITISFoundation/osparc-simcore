# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from asyncio import Future, sleep
from copy import deepcopy
from typing import Dict
from uuid import uuid4

import pytest
import socketio
from aiohttp import web
from mock import call
from yarl import URL

from servicelib.application import create_safe_application
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.director import setup_director
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.resource_manager import (config, registry,
                                                        setup_resource_manager)
from simcore_service_webserver.resource_manager.registry import get_registry
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio import setup_sockets
from simcore_service_webserver.users import setup_users
from simcore_service_webserver.utils import now_str
from utils_assert import assert_status
from utils_login import LoggedUser
from utils_projects import NewProject

API_VERSION = "v0"
GARBAGE_COLLECTOR_INTERVAL = 5


@pytest.fixture
def client(mocked_director_handler, loop, aiohttp_client, app_cfg, postgres_service):
    cfg = deepcopy(app_cfg)

    assert cfg["rest"]["version"] == API_VERSION
    assert cfg["rest"]["enabled"]
    cfg["db"]["init_tables"] = True  # inits postgres_service
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True
    cfg[config.CONFIG_SECTION_NAME]["garbage_collection_interval_seconds"] = GARBAGE_COLLECTOR_INTERVAL # increase speed of garbage collection

    # fake config
    app = create_safe_application(cfg)

    # activates only security+restAPI sub-modules
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_sockets(app)
    setup_projects(app)
    setup_director(app)
    assert setup_resource_manager(app)

    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': cfg["main"]["port"],
        'host': cfg['main']['host']
    }))


@pytest.fixture()
async def logged_user(client, user_role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds=user_role != UserRole.ANONYMOUS
    ) as user:
        print("-----> logged in user", user_role)
        yield user
        print("<----- logged out user", user_role)

@pytest.fixture()
async def logged_user2(client, user_role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds=user_role != UserRole.ANONYMOUS
    ) as user:
        print("-----> logged in user", user_role)
        yield user
        print("<----- logged out user", user_role)




@pytest.fixture
async def empty_user_project(client, empty_project, logged_user):
    project = empty_project()
    async with NewProject(
        project,
        client.app,
        user_id=logged_user["id"]
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])

@pytest.fixture
async def empty_user_project2(client, empty_project, logged_user):
    project = empty_project()
    async with NewProject(
        project,
        client.app,
        user_id=logged_user["id"]
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])




# ------------------------ UTILS ----------------------------------
def set_service_deletion_delay(delay: int, app: web.Application):
    app[config.APP_CONFIG_KEY][config.CONFIG_SECTION_NAME]["resource_deletion_timeout_seconds"] = delay

async def open_project(client, project_uuid: str, client_session_id: str) -> None:
    url = client.app.router["open_project"].url_for(project_id=project_uuid)
    resp = await client.post(url, json=client_session_id)
    await assert_status(resp, web.HTTPOk)

async def close_project(client, project_uuid: str, client_session_id: str) -> None:
    url = client.app.router["close_project"].url_for(project_id=project_uuid)
    resp = await client.post(url, json=client_session_id)
    await assert_status(resp, web.HTTPNoContent)

# ------------------------ TESTS -------------------------------
async def test_anonymous_websocket_connection(socketio_client, client_session_id):
    with pytest.raises(socketio.exceptions.ConnectionError):
        await socketio_client(client_session_id())

@pytest.mark.parametrize("user_role", [
    # (UserRole.ANONYMOUS),
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_websocket_resource_management(client, logged_user, socketio_client, client_session_id):
    app = client.server.app
    socket_registry = get_registry(app)
    cur_client_session_id = client_session_id()
    sio = await socketio_client(cur_client_session_id)
    sid = sio.sid
    resource_key = {"user_id":str(logged_user["id"]), "client_session_id": cur_client_session_id}
    assert await socket_registry.find_keys(("socket_id", sio.sid)) == [resource_key]
    assert sio.sid in await socket_registry.find_resources(resource_key, "socket_id")
    assert len(await socket_registry.find_resources(resource_key, "socket_id")) == 1
    # NOTE: the socket.io client needs the websockets package in order to upgrade to websocket transport
    await sio.disconnect()
    assert not sio.sid
    assert not await socket_registry.find_keys(("socket_id", sio.sid))
    assert not sid in await socket_registry.find_resources(resource_key, "socket_id")
    assert not await socket_registry.find_resources(resource_key, "socket_id")

@pytest.mark.parametrize("user_role", [
    # (UserRole.ANONYMOUS),
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_websocket_multiple_connections(client, logged_user, socketio_client, client_session_id):
    app = client.server.app
    socket_registry = get_registry(app)
    NUMBER_OF_SOCKETS = 5
    # connect multiple clients
    clients = []
    for socket in range(NUMBER_OF_SOCKETS):
        cur_client_session_id = client_session_id()
        sio = await socketio_client(cur_client_session_id)
        resource_key = {"user_id": str(logged_user["id"]), "client_session_id": cur_client_session_id}
        assert await socket_registry.find_keys(("socket_id", sio.sid)) == [resource_key]
        assert [sio.sid] == await socket_registry.find_resources(resource_key, "socket_id")
        assert len(await socket_registry.find_resources({"user_id": str(logged_user["id"]), "client_session_id": "*"}, "socket_id")) == (socket+1)
        clients.append(sio)

    # NOTE: the socket.io client needs the websockets package in order to upgrade to websocket transport
    # disconnect multiple clients
    for sio in clients:
        sid = sio.sid
        await sio.disconnect()
        assert not sio.sid
        assert not await socket_registry.find_keys(("socket_id", sio.sid))
        assert not sid in await socket_registry.find_resources(resource_key, "socket_id")

    assert not await socket_registry.find_resources(resource_key, "socket_id")


@pytest.mark.parametrize("user_role,expected", [
    # (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_websocket_disconnected_after_logout(client, logged_user, socketio_client, client_session_id, expected):
    app = client.server.app
    socket_registry = get_registry(app)

    cur_client_session_id1 = client_session_id()
    sio = await socketio_client(cur_client_session_id1)
    cur_client_session_id2 = client_session_id()
    sio2 = await socketio_client(cur_client_session_id2)
    # logout
    logout_url = client.app.router['auth_logout'].url_for()
    r = await client.post(logout_url)
    assert r.url_obj.path == logout_url.path
    await assert_status(r, expected)

    assert not sio.sid
    # second socket also closed
    assert not sio2.sid


@pytest.mark.parametrize("user_role", [
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_interactive_services_removed_after_logout(loop, client, logged_user, empty_user_project, mocked_director_api, mocked_dynamic_service, client_session_id, socketio_client):
    SERVICE_DELETION_DELAY = 5
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)
    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # create dynamic service - mocked_dynamic_service fixture
    service = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    # create websocket
    client_session_id1 = client_session_id()
    sio = await socketio_client(client_session_id1)
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # logout
    logout_url = client.app.router['auth_logout'].url_for()
    r = await client.post(logout_url)
    assert r.url_obj.path == logout_url.path
    await assert_status(r, web.HTTPOk)
    # ensure sufficient time is wasted here
    await sleep(SERVICE_DELETION_DELAY+GARBAGE_COLLECTOR_INTERVAL)
    # assert dynamic service is removed
    calls = [call(client.server.app, service["service_uuid"])]
    mocked_director_api["stop_service"].assert_has_calls(calls)


@pytest.mark.parametrize("user_role, expected", [
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_interactive_services_remain_after_websocket_reconnection_from_2_tabs(loop, client, logged_user, expected, empty_user_project, mocked_director_api, mocked_dynamic_service, socketio_client, client_session_id):
    SERVICE_DELETION_DELAY = 5
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)

    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # create dynamic service - mocked_dynamic_service fixture
    service = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    # create first websocket
    client_session_id1 = client_session_id()
    sio = await socketio_client(client_session_id1)
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], client_session_id1)

    # create second websocket
    client_session_id2 = client_session_id()
    sio2 = await socketio_client(client_session_id2)
    assert sio.sid != sio2.sid
    # open project in second client
    await open_project(client, empty_user_project["uuid"], client_session_id2)
    # disconnect first websocket
    await sio.disconnect()
    assert not sio.sid
    # ensure sufficient time is wasted here
    await sleep(SERVICE_DELETION_DELAY+GARBAGE_COLLECTOR_INTERVAL)
    # assert dynamic service is still around
    mocked_director_api["stop_service"].assert_not_called()
    # disconnect second websocket
    await sio2.disconnect()
    assert not sio2.sid
    # ensure we wait less than the deletion delay time
    await sleep(SERVICE_DELETION_DELAY/3.0)
    # assert dynamic service is still around for now
    mocked_director_api["stop_service"].assert_not_called()
    # reconnect websocket
    sio2 = await socketio_client(client_session_id2)
    # assert dynamic service is still around
    mocked_director_api["stop_service"].assert_not_called()
    # event after waiting some time
    await sleep(SERVICE_DELETION_DELAY+1)
    mocked_director_api["stop_service"].assert_not_called()
    # now really disconnect
    await sio2.disconnect()
    assert not sio2.sid
    # we need to wait for the service deletion delay
    await sleep(SERVICE_DELETION_DELAY+GARBAGE_COLLECTOR_INTERVAL+1)
    # assert dynamic service is gone
    calls = [call(client.server.app, service["service_uuid"])]
    mocked_director_api["stop_service"].assert_has_calls(calls)

@pytest.mark.parametrize("user_role", [
    # (UserRole.ANONYMOUS),
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_interactive_services_removed_per_project(loop, client, logged_user, empty_user_project, empty_user_project2, mocked_director_api, mocked_dynamic_service, socketio_client, client_session_id):
    SERVICE_DELETION_DELAY = 5
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)
    # create server with delay set to DELAY
    # login - logged_user fixture
    # create empty study1 in project1 - empty_user_project fixture
    # create empty study2 in project2- empty_user_project2 fixture
    # service1 in project1 = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    # service2 in project2 = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    # service3 in project2 = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    service = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    service2 = await mocked_dynamic_service(logged_user["id"], empty_user_project2["uuid"])
    service3 = await mocked_dynamic_service(logged_user["id"], empty_user_project2["uuid"])
    # create websocket1 from tab1
    client_session_id1 = client_session_id()
    sio1 = await socketio_client(client_session_id1)
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # create websocket2 from tab2
    client_session_id2 = client_session_id()
    sio2 = await socketio_client(client_session_id2)
    await open_project(client, empty_user_project2["uuid"], client_session_id2)
    # disconnect websocket1
    await sio1.disconnect()
    assert not sio1.sid
    # assert dynamic service is still around
    mocked_director_api["stop_service"].assert_not_called()
    # wait the defined delay
    await sleep(SERVICE_DELETION_DELAY+GARBAGE_COLLECTOR_INTERVAL)
    # assert dynamic service 1 is removed
    calls = [call(client.server.app, service["service_uuid"])]
    mocked_director_api["stop_service"].assert_has_calls(calls)
    mocked_director_api["stop_service"].reset_mock()

    # disconnect websocket2
    await sio2.disconnect()
    assert not sio2.sid
    # assert dynamic services are still around
    mocked_director_api["stop_service"].assert_not_called()
    # wait the defined delay
    await sleep(SERVICE_DELETION_DELAY+GARBAGE_COLLECTOR_INTERVAL)
    # assert dynamic service 2,3 is removed
    calls = [call(client.server.app, service2["service_uuid"]),
            call(client.server.app, service3["service_uuid"])]
    mocked_director_api["stop_service"].assert_has_calls(calls)
    mocked_director_api["stop_service"].reset_mock()

@pytest.mark.parametrize("user_role", [
    # (UserRole.ANONYMOUS),
    # (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_services_remain_after_closing_one_out_of_two_tabs(loop, client, logged_user, empty_user_project, empty_user_project2, mocked_director_api, mocked_dynamic_service, socketio_client, client_session_id):
    SERVICE_DELETION_DELAY = 1
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)
    # create server with delay set to DELAY
    # login - logged_user fixture
    # create empty study in project - empty_user_project fixture
    # service in project = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    service = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    # open project in tab1
    client_session_id1 = client_session_id()
    sio1 = await socketio_client(client_session_id1)
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # open project in tab2
    client_session_id2 = client_session_id()
    sio2 = await socketio_client(client_session_id2)
    await open_project(client, empty_user_project["uuid"], client_session_id2)
    # close project in tab1
    await close_project(client, empty_user_project["uuid"], client_session_id1)
    # wait the defined delay
    await sleep(SERVICE_DELETION_DELAY+GARBAGE_COLLECTOR_INTERVAL)
    # assert dynamic service is still around
    mocked_director_api["stop_service"].assert_not_called()
    # close project in tab2
    await close_project(client, empty_user_project["uuid"], client_session_id2)
    # wait the defined delay
    await sleep(SERVICE_DELETION_DELAY+GARBAGE_COLLECTOR_INTERVAL)
    mocked_director_api["stop_service"].assert_has_calls([
        call(client.server.app, service["service_uuid"])
    ])
