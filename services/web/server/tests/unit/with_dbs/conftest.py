""" Configuration for unit testing with a postgress fixture

    - Unit testing of webserver app with a postgress service as fixture
    - Starts test session by running a postgres container as a fixture (see postgress_service)

    IMPORTANT: remember that these are still unit-tests!
"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import os
import sys
from asyncio import Future
from copy import deepcopy
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import uuid4

import aioredis
import pytest
import redis
import socketio
import sqlalchemy as sa
import trafaret_config
from aiohttp import web
from pydantic import BaseSettings
from yarl import URL

import simcore_postgres_database.cli as pg_cli
import simcore_service_webserver.db_models as orm
import simcore_service_webserver.utils
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import NewUser
from pytest_simcore.helpers.utils_mock import future_with_result
from servicelib.aiopg_utils import DSN
from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.application import create_application
from simcore_service_webserver.application_config import app_schema as app_schema
from simcore_service_webserver.groups_api import (
    add_user_in_group,
    create_user_group,
    delete_user_group,
    list_user_groups,
)

# current directory
current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


# DEPLOYED SERVICES FOR TESTSUITE SESSION -----------------------------------


@pytest.fixture(scope="session")
def default_app_cfg(osparc_simcore_root_dir, fake_static_dir):
    # NOTE: ONLY used at the session scopes
    cfg_path = current_dir / "config.yaml"
    assert cfg_path.exists()

    variables = dict(os.environ)
    variables.update(
        {
            "OSPARC_SIMCORE_REPO_ROOTDIR": str(osparc_simcore_root_dir),
        }
    )

    # validates and fills all defaults/optional entries that normal load would not do
    cfg_dict = trafaret_config.read_and_validate(cfg_path, app_schema, vars=variables)

    assert Path(cfg_dict["main"]["client_outdir"]) == fake_static_dir

    # WARNING: changes to this fixture during testing propagates to other tests. Use cfg = deepcopy(cfg_dict)
    # FIXME:  free cfg_dict but deepcopy shall be r/w
    return cfg_dict


@pytest.fixture(scope="session")
def docker_compose_file(default_app_cfg):
    """Overrides pytest-docker fixture"""
    old = os.environ.copy()

    cfg = deepcopy(default_app_cfg["db"]["postgres"])

    # docker-compose reads these environs
    os.environ["TEST_POSTGRES_DB"] = cfg["database"]
    os.environ["TEST_POSTGRES_USER"] = cfg["user"]
    os.environ["TEST_POSTGRES_PASSWORD"] = cfg["password"]

    dc_path = current_dir / "docker-compose-devel.yml"

    assert dc_path.exists()
    yield str(dc_path)

    os.environ = old


# WEB SERVER/CLIENT FIXTURES ------------------------------------------------


@pytest.fixture(scope="function")
def app_cfg(default_app_cfg, aiohttp_unused_port):
    """Can be overriden in any test module to configure
    the app accordingly
    """
    cfg = deepcopy(default_app_cfg)

    # fills ports on the fly
    cfg["main"]["port"] = aiohttp_unused_port()
    cfg["storage"]["port"] = aiohttp_unused_port()

    # this fixture can be safely modified during test since it is renovated on every call
    return cfg


class _BaseSettingEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, BaseSettings):
            return o.json()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


@pytest.fixture
def web_server(loop, aiohttp_server, app_cfg, monkeypatch, postgres_db):
    # original APP
    app = create_application(app_cfg)

    print(
        "Inits webserver with config",
        json.dumps(app[APP_CONFIG_KEY], indent=2, cls=_BaseSettingEncoder),
    )

    # with patched email
    _path_mail(monkeypatch)

    server = loop.run_until_complete(aiohttp_server(app, port=app_cfg["main"]["port"]))
    return server


@pytest.fixture
def client(loop, aiohttp_client, web_server, mock_orphaned_services):
    client = loop.run_until_complete(aiohttp_client(web_server))
    return client


# SUBSYSTEM MOCKS FIXTURES ------------------------------------------------
#
# Mocks entirely or part of the calls to the web-server subsystems
#


@pytest.fixture
def computational_system_mock(mocker):
    mock_fun = mocker.patch(
        "simcore_service_webserver.projects.projects_handlers.update_pipeline_db",
        return_value=Future(),
    )
    mock_fun.return_value.set_result("")
    return mock_fun


@pytest.fixture
async def storage_subsystem_mock(loop, mocker):
    """
    Patches client calls to storage service

    Patched functions are exposed within projects but call storage subsystem
    """
    # requests storage to copy data
    mock = mocker.patch(
        "simcore_service_webserver.projects.projects_api.copy_data_folders_from_project"
    )

    async def _mock_copy_data_from_project(*args):
        return args[2]

    mock.side_effect = _mock_copy_data_from_project

    # requests storage to delete data
    # mock1 = mocker.patch('simcore_service_webserver.projects.projects_handlers.delete_data_folders_of_project', return_value=None)
    mock1 = mocker.patch(
        "simcore_service_webserver.projects.projects_handlers.projects_api.delete_data_folders_of_project",
        return_value=Future(),
    )
    mock1.return_value.set_result("")
    return mock, mock1


@pytest.fixture
def asyncpg_storage_system_mock(mocker):
    mocked_method = mocker.patch(
        "simcore_service_webserver.login.storage.AsyncpgStorage.delete_user",
        return_value=Future(),
    )
    mocked_method.return_value.set_result("")
    return mocked_method


@pytest.fixture
def mocked_director_subsystem(mocker):
    mock_director_api = {
        "get_running_interactive_services": mocker.patch(
            "simcore_service_webserver.director.director_api.get_running_interactive_services",
            return_value=future_with_result(""),
        ),
        "start_service": mocker.patch(
            "simcore_service_webserver.director.director_api.start_service",
            return_value=future_with_result(""),
        ),
        "stop_service": mocker.patch(
            "simcore_service_webserver.director.director_api.stop_service",
            return_value=future_with_result(""),
        ),
    }
    return mock_director_api


@pytest.fixture
async def mocked_director_api(loop, mocker):
    mocks = {}
    mocked_running_services = mocker.patch(
        "simcore_service_webserver.director.director_api.get_running_interactive_services",
        return_value=Future(),
    )
    mocked_running_services.return_value.set_result("")
    mocks["get_running_interactive_services"] = mocked_running_services
    mocked_stop_service = mocker.patch(
        "simcore_service_webserver.director.director_api.stop_service",
        return_value=Future(),
    )
    mocked_stop_service.return_value.set_result("")
    mocks["stop_service"] = mocked_stop_service

    yield mocks


@pytest.fixture
async def mocked_dynamic_service(loop, client, mocked_director_api):
    services = []

    async def create(user_id, project_id) -> Dict:
        SERVICE_UUID = str(uuid4())
        SERVICE_KEY = "simcore/services/dynamic/3d-viewer"
        SERVICE_VERSION = "1.4.2"
        url = client.app.router["create_node"].url_for(project_id=project_id)
        create_node_data = {
            "service_key": SERVICE_KEY,
            "service_version": SERVICE_VERSION,
            "service_uuid": SERVICE_UUID,
        }

        running_service_dict = {
            "published_port": "23423",
            "service_uuid": SERVICE_UUID,
            "service_key": SERVICE_KEY,
            "service_version": SERVICE_VERSION,
            "service_host": "some_service_host",
            "service_port": "some_service_port",
            "service_state": "some_service_state",
        }

        services.append(running_service_dict)
        # reset the future or an invalidStateError will appear as set_result sets the future to done
        mocked_director_api["get_running_interactive_services"].return_value = Future()
        mocked_director_api["get_running_interactive_services"].return_value.set_result(
            services
        )
        return running_service_dict

    return create


# POSTGRES CORE SERVICE ---------------------------------------------------


@pytest.fixture(scope="session")
def postgres_dsn(docker_services, docker_ip, default_app_cfg: Dict) -> Dict:
    cfg = deepcopy(default_app_cfg["db"]["postgres"])
    cfg["host"] = docker_ip
    cfg["port"] = docker_services.port_for("postgres", 5432)
    return cfg


@pytest.fixture(scope="session")
def postgres_service(docker_services, postgres_dsn):
    url = DSN.format(**postgres_dsn)

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: _is_postgres_responsive(url),
        timeout=30.0,
        pause=0.1,
    )

    return url


@pytest.fixture
def postgres_db(
    app_cfg: Dict, postgres_dsn: Dict, postgres_service: str
) -> sa.engine.Engine:
    url = postgres_service

    # Configures db and initializes tables
    pg_cli.discover.callback(**postgres_dsn)
    pg_cli.upgrade.callback("head")
    # Uses syncrounous engine for that
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")

    yield engine

    pg_cli.downgrade.callback("base")
    pg_cli.clean.callback()

    orm.metadata.drop_all(engine)
    engine.dispose()


# REDIS CORE SERVICE ------------------------------------------------------


@pytest.fixture(scope="session")
def redis_service(docker_services, docker_ip):

    host = docker_ip
    port = docker_services.port_for("redis", 6379)
    url = URL(f"redis://{host}:{port}")

    docker_services.wait_until_responsive(
        check=lambda: _is_redis_responsive(host, port),
        timeout=30.0,
        pause=0.1,
    )
    return url


@pytest.fixture
async def redis_client(loop, redis_service):
    client = await aioredis.create_redis_pool(str(redis_service), encoding="utf-8")
    yield client

    await client.flushall()
    client.close()
    await client.wait_closed()


def _is_redis_responsive(host: str, port: int) -> bool:
    r = redis.Redis(host=host, port=port)
    return r.ping() == True


# SOCKETS FIXTURES  --------------------------------------------------------


@pytest.fixture()
def socketio_url(client) -> Callable:
    def create_url(client_override: Optional = None) -> str:
        SOCKET_IO_PATH = "/socket.io/"
        return str((client_override or client).make_url(SOCKET_IO_PATH))

    yield create_url


@pytest.fixture()
async def security_cookie_factory(client) -> Callable:
    async def creator(client_override: Optional = None) -> str:
        # get the cookie by calling the root entrypoint
        resp = await (client_override or client).get("/v0/")
        data, error = await assert_status(resp, web.HTTPOk)
        assert data
        assert not error

        cookie = (
            resp.request_info.headers["Cookie"]
            if "Cookie" in resp.request_info.headers
            else ""
        )
        return cookie

    yield creator


@pytest.fixture()
async def socketio_client(
    socketio_url: Callable, security_cookie_factory: Callable
) -> Callable:
    clients = []

    async def connect(
        client_session_id: str, client: Optional = None
    ) -> socketio.AsyncClient:
        sio = socketio.AsyncClient(ssl_verify=False)
        # enginio 3.10.0 introduced ssl verification
        url = str(
            URL(socketio_url(client)).with_query(
                {"client_session_id": client_session_id}
            )
        )
        headers = {}
        cookie = await security_cookie_factory(client)
        if cookie:
            # WARNING: engineio fails with empty cookies. Expects "key=value"
            headers.update({"Cookie": cookie})

        await sio.connect(url, headers=headers)
        assert sio.sid
        clients.append(sio)
        return sio

    yield connect

    for sio in clients:
        await sio.disconnect()
        assert not sio.sid


@pytest.fixture()
def client_session_id() -> str:
    def create() -> str():
        return str(uuid4())

    return create


# USER GROUP FIXTURES -------------------------------------------------------


@pytest.fixture
async def primary_group(client, logged_user) -> Dict[str, str]:
    primary_group, _, _ = await list_user_groups(client.app, logged_user["id"])
    return primary_group


@pytest.fixture
async def standard_groups(client, logged_user: Dict) -> List[Dict[str, str]]:
    # create a separate admin account to create some standard groups for the logged user
    sparc_group = {
        "gid": "5",  # this will be replaced
        "label": "SPARC",
        "description": "Stimulating Peripheral Activity to Relieve Conditions",
        "thumbnail": "https://commonfund.nih.gov/sites/default/files/sparc-image-homepage500px.png",
        "inclusionRules": {"email": r"@(sparc)+\.(io|com)$"},
    }
    team_black_group = {
        "gid": "5",  # this will be replaced
        "label": "team Black",
        "description": "THE incredible black team",
        "thumbnail": None,
        "inclusionRules": {"email": r"@(black)+\.(io|com)$"},
    }
    async with NewUser(
        {"name": f"{logged_user['name']}_admin", "role": "USER"}, client.app
    ) as admin_user:
        # creates two groups
        sparc_group = await create_user_group(client.app, admin_user["id"], sparc_group)
        team_black_group = await create_user_group(
            client.app, admin_user["id"], team_black_group
        )

        # adds logged_user  to sparc group
        await add_user_in_group(
            client.app,
            admin_user["id"],
            sparc_group["gid"],
            new_user_id=logged_user["id"],
        )

        # adds logged_user  to team-black group
        await add_user_in_group(
            client.app,
            admin_user["id"],
            team_black_group["gid"],
            new_user_email=logged_user["email"],
        )

        _, standard_groups, _ = await list_user_groups(client.app, logged_user["id"])
        yield standard_groups
        # clean groups
        await delete_user_group(client.app, admin_user["id"], sparc_group["gid"])
        await delete_user_group(client.app, admin_user["id"], team_black_group["gid"])


@pytest.fixture
async def all_group(client, logged_user) -> Dict[str, str]:
    _, _, all_group = await list_user_groups(client.app, logged_user["id"])
    return all_group


# GENERIC HELPER FUNCTIONS ----------------------------------------------------


def _path_mail(monkeypatch):
    async def send_mail(*args):
        print("=== EMAIL TO: {}\n=== SUBJECT: {}\n=== BODY:\n{}".format(*args))

    monkeypatch.setattr(
        simcore_service_webserver.login.utils, "compose_mail", send_mail
    )


def _is_postgres_responsive(url):
    """Check if something responds to ``url`` """
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True
