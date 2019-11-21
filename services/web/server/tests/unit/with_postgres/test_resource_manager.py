# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from asyncio import Future, sleep
from copy import deepcopy

import pytest
import socketio
from aiohttp import web

from servicelib.application import create_safe_application
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.director import setup_director
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.resource_manager import (config,
                                                        setup_resource_manager)
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio import registry, setup_sockets
from simcore_service_webserver.socketio.config import get_socket_registry
from simcore_service_webserver.users import setup_users
from simcore_service_webserver.utils import now_str
from utils_assert import assert_status
from utils_login import LoggedUser
from utils_projects import NewProject

API_VERSION = "v0"


@pytest.fixture
async def mocked_director_handlers(loop, mocker):
    # Note: this needs to be activated before the setup takes place
    mocks = {}
    running_service_dict = {
        "published_port": "23423",
        "service_uuid": "some_service_uuid",
        "service_key": "some_service_key",
        "service_version": "some_service_version",
        "service_host": "some_service_host",
        "service_port": "some_service_port",
        "service_state": "some_service_state"
    }
    mocked_director_running_interactive_services_post_handler = \
        mocker.patch('simcore_service_webserver.director.handlers.running_interactive_services_post',
                     return_value=web.json_response({"data": running_service_dict}, status=web.HTTPCreated.status_code))
    mocks["running_interactive_services_post"] = mocked_director_running_interactive_services_post_handler
    mocked_director_delete_all_services_fct = mocker.patch(
        'simcore_service_webserver.director.handlers._delete_all_services')
    mocks["_delete_all_services"] = mocked_director_delete_all_services_fct
    yield mocks


@pytest.fixture
def client(mocked_director_handlers, loop, aiohttp_client, app_cfg, postgres_service):
    cfg = deepcopy(app_cfg)

    assert cfg["rest"]["version"] == API_VERSION
    assert API_VERSION in cfg["rest"]["location"]
    cfg["db"]["init_tables"] = True  # inits postgres_service
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True

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
    setup_resource_manager(app)

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
    empty_project = {
        "uuid": "0000000-invalid-uuid",
        "name": "Empty name",
        "description": "some description of an empty project",
        "prjOwner": "I'm the empty project owner, hi!",
        "creationDate": now_str(),
        "lastChangeDate": now_str(),
        "thumbnail": "",
        "workbench": {}
    }
    yield empty_project


@pytest.fixture
async def empty_user_project(client, empty_project, logged_user):
    async with NewProject(
        empty_project,
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

    async def connect():
        sio = socketio.AsyncClient()
        await sio.connect(socketio_url, headers={'Cookie': security_cookie})
        clients.append(sio)
        return sio
    yield connect
    for sio in clients:
        await sio.disconnect()


@pytest.fixture
async def mocked_dynamic_service(loop, client, logged_user, empty_user_project, mocked_director_handlers):
    SERVICE_UUID = "some_uuid"
    url = client.app.router["running_interactive_services_post"].url_for().with_query(
        {
            "user_id": logged_user["id"],
            "project_id": empty_user_project["uuid"],
            "service_key": "simcore/services/dynamic/3d-viewer",
            "service_tag": "1.4.2",
            "service_uuid": SERVICE_UUID
        })

    resp = await client.post(url)
    data, _error = await assert_status(resp, expected_cls=web.HTTPCreated)
    mocked_director_handlers["running_interactive_services_post"].assert_called_once(
    )


@pytest.mark.parametrize("user_role", [
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_interactive_services_removed_after_logout(loop, client, mocked_dynamic_service, mocked_director_handlers):
    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # create dynamic service - mocked_dynamic_service fixture
    # logout
    logout_url = client.app.router['auth_logout'].url_for()
    r = await client.get(logout_url)
    assert r.url_obj.path == logout_url.path
    await assert_status(r, web.HTTPOk)
    # assert dynamic service is removed
    mocked_director_handlers["_delete_all_services"].assert_called_once()


def set_service_deletion_delay(delay: int, app: web.Application):
    app[config.APP_CONFIG_KEY][config.CONFIG_SECTION_NAME]["service_deletion_timeout_seconds"] = delay


@pytest.mark.parametrize("user_role", [
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_interactive_services_remain_after_websocket_reconnection(loop, client, mocked_dynamic_service, mocked_director_handlers, socketio_client):
    SERVICE_DELETION_DELAY = 5
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)
    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # create dynamic service - mocked_dynamic_service fixture
    # create first websocket
    sio = await socketio_client()
    assert sio.sid
    # create second websocket
    sio2 = await socketio_client()
    assert sio2.sid
    assert sio.sid != sio2.sid
    # disconnect first websocket
    await sio.disconnect()
    # ensure sufficient time is wasted here
    await sleep(SERVICE_DELETION_DELAY+1)
    # assert dynamic service is still around
    mocked_director_handlers["_delete_all_services"].assert_not_called()
    # disconnect second websocket
    await sio2.disconnect()
    # ensure we wait less than the deletion delay time
    await sleep(SERVICE_DELETION_DELAY/3.0)
    # assert dynamic service is still around for now
    mocked_director_handlers["_delete_all_services"].assert_not_called()
    # reconnect websocket
    sio = await socketio_client()
    assert sio.sid
    # assert dynamic service is still around
    mocked_director_handlers["_delete_all_services"].assert_not_called()
    await sleep(SERVICE_DELETION_DELAY+1)
    # assert dynamic service is still around
    mocked_director_handlers["_delete_all_services"].assert_not_called()


@pytest.mark.parametrize("user_role", [
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_interactive_services_removed_after_websocket_disconnection_for_some_time(loop, client, mocked_dynamic_service, mocked_director_handlers, socketio_client):
    SERVICE_DELETION_DELAY = 5
    set_service_deletion_delay(SERVICE_DELETION_DELAY, client.server.app)
    # create server with delay set to DELAY
    # login - logged_user fixture
    # create empty study - empty_user_project fixture
    # create dynamic service - mocked_dynamic_service fixture
    # create websocket
    sio = await socketio_client()
    assert sio.sid
    # disconnect websocket
    await sio.disconnect()
    # assert dynamic service is still around
    mocked_director_handlers["_delete_all_services"].assert_not_called()
    # wait the defined delay
    await sleep(SERVICE_DELETION_DELAY+1)
    # assert dynamic service is removed
    mocked_director_handlers["_delete_all_services"].assert_called_once()
