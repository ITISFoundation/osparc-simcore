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
async def mocked_director_handler(loop, mocker):
    # Note: this needs to be activated before the setup takes place
    running_service_dict = {
        "published_port": "23423",
        "service_uuid": "some_service_uuid",
        "service_key": "some_service_key",
        "service_version": "some_service_version",
        "service_host": "some_service_host",
        "service_port": "some_service_port",
        "service_state": "some_service_state"
    }
    mock = mocker.patch('simcore_service_webserver.director.handlers.running_interactive_services_post',
                     return_value=web.json_response({"data": running_service_dict}, status=web.HTTPCreated.status_code))
    yield mock

@pytest.fixture
async def mocked_director_api(loop, mocker):
    mocks = {}
    mocked_running_services = mocker.patch('simcore_service_webserver.director.director_api.get_running_interactive_services',
                                        return_value=Future())
    mocked_running_services.return_value.set_result("")
    mocks["get_running_interactive_services"] = mocked_running_services
    mocked_stop_service = mocker.patch('simcore_service_webserver.director.director_api.stop_service',
                    return_value=Future())
    mocked_stop_service.return_value.set_result("")
    mocks["stop_service"] = mocked_stop_service
    yield mocks

@pytest.fixture
def client(mocked_director_handler, loop, aiohttp_client, app_cfg, postgres_service):
    cfg = deepcopy(app_cfg)

    assert cfg["rest"]["version"] == API_VERSION
    assert API_VERSION in cfg["rest"]["location"]
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


@pytest.fixture
def empty_project():
    def create():
        empty_project = {
            "uuid": f"project-{uuid4()}",
            "name": "Empty name",
            "description": "some description of an empty project",
            "prjOwner": "I'm the empty project owner, hi!",
            "creationDate": now_str(),
            "lastChangeDate": now_str(),
            "thumbnail": "",
            "workbench": {}
        }
        return empty_project
    return create


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


@pytest.fixture()
async def security_cookie(client) -> str:
    # get the cookie by calling the root entrypoint
    resp = await client.get("/v0/")
    payload = await resp.json()
    assert resp.status == 200, str(payload)
    data, error = unwrap_envelope(payload)
    assert data
    assert not error

    cookie = ""
    if "Cookie" in resp.request_info.headers:
        cookie = resp.request_info.headers["Cookie"]
    yield cookie


@pytest.fixture()
async def socketio_url(client) -> str:
    SOCKET_IO_PATH = '/socket.io/'
    return str(client.make_url(SOCKET_IO_PATH))


@pytest.fixture()
async def socketio_client(socketio_url: str, security_cookie: str):
    clients = []

    async def connect(tab_id):
        sio = socketio.AsyncClient()
        url = str(URL(socketio_url).with_query({'tabid': tab_id}))
        await sio.connect(url, headers={'Cookie': security_cookie})
        assert sio.sid
        clients.append(sio)
        return sio
    yield connect
    for sio in clients:
        await sio.disconnect()
        assert not sio.sid

@pytest.fixture()
def tab_id():
    def create() -> str():
        return str(uuid4())
    return create


@pytest.fixture
async def mocked_dynamic_service(loop, client, mocked_director_handler, mocked_director_api):
    services = {}
    async def create(user_id, project_id) -> Dict:
        SERVICE_UUID = str(uuid4())
        SERVICE_KEY = "simcore/services/dynamic/3d-viewer"
        SERVICE_VERSION = "1.4.2"
        url = client.app.router["running_interactive_services_post"].url_for().with_query(
            {
                "user_id": user_id,
                "project_id": project_id,
                "service_key": SERVICE_KEY,
                "service_tag": SERVICE_VERSION,
                "service_uuid": SERVICE_UUID
            })

        running_service_dict = {
            "published_port": "23423",
            "service_uuid": SERVICE_UUID,
            "service_key": SERVICE_KEY,
            "service_version": SERVICE_VERSION,
            "service_host": "some_service_host",
            "service_port": "some_service_port",
            "service_state": "some_service_state"
        }

        mocked_director_handler.return_value = web.json_response({"data": running_service_dict}, status=web.HTTPCreated.status_code)
        mocked_director_handler.reset_mock()
        resp = await client.post(url)
        data, _error = await assert_status(resp, expected_cls=web.HTTPCreated)
        mocked_director_handler.assert_called_once()

        services.update({SERVICE_UUID: running_service_dict})
        # reset the future or an invalidStateError will appear as set_result sets the future to done
        mocked_director_api["get_running_interactive_services"].return_value = Future()
        mocked_director_api["get_running_interactive_services"].return_value.set_result(services)
        return running_service_dict
    return create

# ------------------------ UTILS ----------------------------------
def set_service_deletion_delay(delay: int, app: web.Application):
    app[config.APP_CONFIG_KEY][config.CONFIG_SECTION_NAME]["resource_deletion_timeout_seconds"] = delay

async def open_project(client, project_uuid: str, tab_id: str) -> None:
    url = client.app.router["open_project"].url_for(project_id=project_uuid)
    resp = await client.post(url, json=tab_id)
    await assert_status(resp, web.HTTPOk)

# ------------------------ TESTS -------------------------------
async def test_anonymous_websocket_connection(socketio_client, tab_id):
    with pytest.raises(socketio.exceptions.ConnectionError):
        await socketio_client(tab_id())

@pytest.mark.parametrize("user_role", [
    # (UserRole.ANONYMOUS),
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_websocket_resource_management(client, logged_user, socketio_client, tab_id):
    app = client.server.app
    socket_registry = get_registry(app)
    cur_tab_id = tab_id()
    sio = await socketio_client(cur_tab_id)
    sid = sio.sid
    resource_key = {"user_id":str(logged_user["id"]), "tab_id": cur_tab_id}
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
async def test_websocket_multiple_connections(client, logged_user, socketio_client, tab_id):
    app = client.server.app
    socket_registry = get_registry(app)
    NUMBER_OF_SOCKETS = 5
    # connect multiple clients
    clients = []
    for socket in range(NUMBER_OF_SOCKETS):
        cur_tab_id = tab_id()
        sio = await socketio_client(cur_tab_id)
        resource_key = {"user_id": str(logged_user["id"]), "tab_id": cur_tab_id}
        assert await socket_registry.find_keys(("socket_id", sio.sid)) == [resource_key]
        assert [sio.sid] == await socket_registry.find_resources(resource_key, "socket_id")
        assert len(await socket_registry.find_resources({"user_id": str(logged_user["id"])}, "socket_id")) == (socket+1)
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
async def test_websocket_disconnected_after_logout(client, logged_user, socketio_client, tab_id, expected):
    app = client.server.app
    socket_registry = get_registry(app)
    cur_tab_id = tab_id()
    sio = await socketio_client(cur_tab_id)
    # logout
    logout_url = client.app.router['auth_logout'].url_for()
    r = await client.get(logout_url)
    assert r.url_obj.path == logout_url.path
    await assert_status(r, expected)

    assert not sio.sid


@pytest.mark.parametrize("user_role", [
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_interactive_services_removed_after_logout(loop, client, logged_user, empty_user_project, mocked_director_api, mocked_dynamic_service):
    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # create dynamic service - mocked_dynamic_service fixture
    service = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    # logout
    logout_url = client.app.router['auth_logout'].url_for()
    r = await client.get(logout_url)
    assert r.url_obj.path == logout_url.path
    await assert_status(r, web.HTTPOk)
    # assert dynamic service is removed
    calls = [call(client.server.app, service["service_uuid"])]
    mocked_director_api["stop_service"].assert_has_calls(calls)


@pytest.mark.parametrize("user_role, expected", [
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_interactive_services_remain_after_websocket_reconnection_from_2_tabs(loop, client, logged_user, expected, empty_user_project, mocked_director_api, mocked_dynamic_service, socketio_client, tab_id):
    SERVICE_DELETION_DELAY = 5
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)

    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # create dynamic service - mocked_dynamic_service fixture
    service = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    # create first websocket
    tab_id1 = tab_id()
    sio = await socketio_client(tab_id1)
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], tab_id1)

    # create second websocket
    tab_id2 = tab_id()
    sio2 = await socketio_client(tab_id2)
    assert sio.sid != sio2.sid
    # open project in second client
    await open_project(client, empty_user_project["uuid"], tab_id2)
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
    sio2 = await socketio_client(tab_id2)
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
async def test_interactive_services_removed_after_websocket_disconnection_for_some_time(loop, client, logged_user, empty_user_project, mocked_director_api, mocked_dynamic_service, socketio_client, tab_id):
    SERVICE_DELETION_DELAY = 3
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)
    # create server with delay set to DELAY
    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # service = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    # create dynamic service - mocked_dynamic_service fixture
    service = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    service2 = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    # create websocket
    cur_tab_id = tab_id()
    sio = await socketio_client(cur_tab_id)
    # open the project
    await open_project(client, empty_user_project["uuid"], cur_tab_id)
    # disconnect websocket
    await sio.disconnect()
    assert not sio.sid
    # assert dynamic service is still around
    mocked_director_api["stop_service"].assert_not_called()
    # wait the defined delay
    await sleep(SERVICE_DELETION_DELAY+GARBAGE_COLLECTOR_INTERVAL)
    # assert dynamic service are removed
    calls = [call(client.server.app, service["service_uuid"]),
            call(client.server.app, service2["service_uuid"])]
    mocked_director_api["stop_service"].assert_has_calls(calls)
    mocked_director_api["stop_service"].reset_mock()

@pytest.mark.parametrize("user_role", [
    # (UserRole.ANONYMOUS),
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_interactive_services_removed_per_tab(loop, client, logged_user, empty_user_project, empty_user_project2, mocked_director_api, mocked_dynamic_service, socketio_client, tab_id):
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
    tab_id1 = tab_id()
    sio1 = await socketio_client(tab_id1)
    await open_project(client, empty_user_project["uuid"], tab_id1)
    # create websocket2 from tab2
    tab_id2 = tab_id()
    sio2 = await socketio_client(tab_id2)
    await open_project(client, empty_user_project2["uuid"], tab_id2)
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
