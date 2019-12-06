# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy
from uuid import uuid4

import pytest
import socketio
from aiohttp import web
from yarl import URL

from servicelib.application import create_safe_application
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.resource_manager import (registry,
                                                        setup_resource_manager)
from simcore_service_webserver.resource_manager.config import get_registry
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio import setup_sockets
from simcore_service_webserver.users import setup_users
from utils_assert import assert_status
from utils_login import LoggedUser

API_VERSION = "v0"

@pytest.fixture
def client(loop, aiohttp_client, app_cfg, postgres_service):
    cfg = deepcopy(app_cfg)

    assert cfg["rest"]["version"] == API_VERSION
    assert API_VERSION in cfg["rest"]["location"]

    cfg["db"]["init_tables"] = True # inits postgres_service

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
        check_if_succeeds = user_role!=UserRole.ANONYMOUS
    ) as user:
        print("-----> logged in user", user_role)
        yield user
        print("<----- logged out user", user_role)


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
        clients.append(sio)
        return sio
    yield connect
    for sio in clients:
        await sio.disconnect()

@pytest.fixture()
async def tab_id() -> str:
    return str(uuid4())

# async def test_anonymous_websocket_connection(client):
async def test_anonymous_websocket_connection(socketio_client, tab_id):
    with pytest.raises(socketio.exceptions.ConnectionError):
        await socketio_client(tab_id)


@pytest.mark.parametrize("user_role", [
    # (UserRole.ANONYMOUS),
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_websocket_connections(client, logged_user, socketio_client, tab_id):
    app = client.server.app
    socket_registry = get_registry(app)

    sio = await socketio_client(tab_id)
    assert await socket_registry.find_owner(sio.sid) == str(logged_user["id"])
    assert sio.sid in await socket_registry.find_sockets(logged_user["id"])
    assert len(await socket_registry.find_sockets(logged_user["id"])) == 1
    # NOTE: the socket.io client needs the websockets package in order to upgrade to websocket transport
    await sio.disconnect()
    assert not await socket_registry.find_owner(sio.sid)
    assert not sio.sid in await socket_registry.find_sockets(logged_user["id"])
    assert not await socket_registry.find_sockets(logged_user["id"])

@pytest.mark.parametrize("user_role", [
    # (UserRole.ANONYMOUS),
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_multiple_websocket_connections(client, logged_user, socketio_client):
    app = client.server.app
    socket_registry = get_registry(app)
    NUMBER_OF_SOCKETS = 5
    # connect multiple clients
    clients = []
    for socket in range(NUMBER_OF_SOCKETS):
        tab_id = str(uuid4())
        sio = await socketio_client(tab_id)
        assert await socket_registry.find_owner(sio.sid) == str(logged_user["id"])
        assert sio.sid in await socket_registry.find_sockets(logged_user["id"])
        assert len(await socket_registry.find_sockets(logged_user["id"])) == (socket+1)
        clients.append(sio)

    # NOTE: the socket.io client needs the websockets package in order to upgrade to websocket transport
    # disconnect multiple clients
    for sio in clients:
        sid = sio.sid
        await sio.disconnect()
        assert not sio.sid
        assert not await socket_registry.find_owner(sio.sid)
        assert not sid in await socket_registry.find_sockets(logged_user["id"])

    assert not await socket_registry.find_sockets(logged_user["id"])
    assert not await socket_registry.find_sockets(logged_user["id"])

@pytest.mark.parametrize("user_role", [
    # (UserRole.ANONYMOUS),
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_websocket_disconnected_after_logout(client, logged_user, socketio_client, tab_id):
    app = client.server.app
    socket_registry = get_registry(app)

    sio = await socketio_client(tab_id)
    # logout
    logout_url = client.app.router['auth_logout'].url_for()
    r = await client.get(logout_url)
    assert r.url_obj.path == logout_url.path
    await assert_status(r, web.HTTPOk)

    assert not sio.sid
