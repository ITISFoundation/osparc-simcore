""" Configuration for unit testing with a postgress fixture

    - Unit testing of webserver app with a postgress service as fixture
    - Starts test session by running a postgres container as a fixture (see postgress_service)

    IMPORTANT: remember that these are still unit-tests!
"""
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import sys
import textwrap
from copy import deepcopy
from pathlib import Path
from typing import AsyncIterator, Callable, Iterator
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import redis
import redis.asyncio as aioredis
import simcore_postgres_database.cli as pg_cli
import simcore_service_webserver.db_models as orm
import simcore_service_webserver.utils
import sqlalchemy as sa
from _helpers import MockedStorageSubsystem
from _pytest.monkeypatch import MonkeyPatch
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pydantic import ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_dict import ConfigDict
from pytest_simcore.helpers.utils_login import NewUser
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.aiohttp.long_running_tasks.client import LRTask
from servicelib.aiohttp.long_running_tasks.server import TaskProgress
from servicelib.common_aiopg_utils import DSN
from settings_library.redis import RedisSettings
from simcore_service_webserver._constants import INDEX_RESOURCE_NAME
from simcore_service_webserver.application import create_application
from simcore_service_webserver.groups_api import (
    add_user_in_group,
    create_user_group,
    delete_user_group,
    list_user_groups,
)

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# DEPLOYED SERVICES FOR TESTSUITE SESSION -----------------------------------


@pytest.fixture(autouse=True)
def disable_swagger_doc_generation(
    monkeypatch: MonkeyPatch, osparc_simcore_root_dir: Path
):
    """
    by not enabling the swagger documentation, 1.8s per test is gained
    """
    monkeypatch.setenv("REST_SWAGGER_API_DOC_ENABLED", "0")


@pytest.fixture(scope="session")
def docker_compose_file(
    default_app_cfg: ConfigDict, monkeypatch_session: MonkeyPatch
) -> str:
    """Overrides pytest-docker fixture"""

    cfg = deepcopy(default_app_cfg["db"]["postgres"])

    # docker-compose reads these environs
    monkeypatch_session.setenv("TEST_POSTGRES_DB", cfg["database"])
    monkeypatch_session.setenv("TEST_POSTGRES_USER", cfg["user"])
    monkeypatch_session.setenv("TEST_POSTGRES_PASSWORD", cfg["password"])

    compose_path = CURRENT_DIR / "docker-compose-devel.yml"

    assert compose_path.exists()
    return f"{compose_path}"


# WEB SERVER/CLIENT FIXTURES ------------------------------------------------


@pytest.fixture
def app_cfg(default_app_cfg: ConfigDict, unused_tcp_port_factory) -> ConfigDict:
    """
    NOTE: SHOULD be overriden in any test module to configure the app accordingly
    """
    cfg = deepcopy(default_app_cfg)
    # fills ports on the fly
    cfg["main"]["port"] = unused_tcp_port_factory()
    cfg["storage"]["port"] = unused_tcp_port_factory()

    # this fixture can be safely modified during test since it is renovated on every call
    return cfg


@pytest.fixture
def app_environment(
    app_cfg: ConfigDict,
    monkeypatch_setenv_from_app_config: Callable[[ConfigDict], dict[str, str]],
) -> dict[str, str]:
    """overridable fixture that defines the ENV for the webserver application
    based on legacy application config files.

    override like so:
    @pytest.fixture
    def app_environment(app_environment: dict[str, str], monkeypatch: MonkeyPatch) -> dict[str, str]:
        monkeypatch.setenv("MODIFIED_ENV", "VALUE")
        return app_environment | {"MODIFIED_ENV":"VALUE"}
    """
    print("+ web_server:")
    cfg = deepcopy(app_cfg)
    return monkeypatch_setenv_from_app_config(cfg)


@pytest.fixture
def web_server(
    event_loop: asyncio.AbstractEventLoop,
    app_cfg: ConfigDict,
    app_environment,
    postgres_db: sa.engine.Engine,
    # tools
    aiohttp_server: Callable,
    monkeypatch: MonkeyPatch,
    disable_static_webserver: Callable,
) -> TestServer:
    # original APP
    app = create_application()

    # with patched email
    _patch_compose_mail(monkeypatch)

    disable_static_webserver(app)

    server = event_loop.run_until_complete(
        aiohttp_server(app, port=app_cfg["main"]["port"])
    )

    assert isinstance(postgres_db, sa.engine.Engine)
    pg_settings = dict(e.split("=") for e in app[APP_DB_ENGINE_KEY].dsn.split())
    assert pg_settings["host"] == postgres_db.url.host
    assert int(pg_settings["port"]) == postgres_db.url.port
    assert pg_settings["user"] == postgres_db.url.username

    return server


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client,
    web_server: TestServer,
    mock_orphaned_services,
) -> TestClient:
    cli = event_loop.run_until_complete(aiohttp_client(web_server))
    return cli


# SUBSYSTEM MOCKS FIXTURES ------------------------------------------------
#
# Mocks entirely or part of the calls to the web-server subsystems
#


@pytest.fixture
def disable_static_webserver(monkeypatch: MonkeyPatch) -> Callable:
    """
    Disables the static-webserver module.
    Avoids fecthing and caching index.html pages
    Mocking a response for all the services which expect it.
    """

    async def _mocked_index_html(request: web.Request) -> web.Response:
        """
        Emulates the reply of the '/' path when the static-webserver is disabled
        """
        html = textwrap.dedent(
            f"""\
            <!DOCTYPE html>
            <html>
            <body>
                <h1>OSPARC-SIMCORE</h1>
                <p> This is a result of disable_static_webserver fixture for product OSPARC ({__file__})</p>
            </body>
            </html>
            """
        )
        return web.Response(text=html)

    # mount and serve some staic mocked content
    monkeypatch.setenv("WEBSERVER_STATICWEB", "null")

    def add_index_route(app: web.Application) -> None:
        app.router.add_get("/", _mocked_index_html, name=INDEX_RESOURCE_NAME)

    return add_index_route


@pytest.fixture
async def storage_subsystem_mock(mocker) -> MockedStorageSubsystem:
    """
    Patches client calls to storage service

    Patched functions are exposed within projects but call storage subsystem
    """

    async def _mock_copy_data_from_project(app, src_prj, dst_prj, nodes_map, user_id):
        print(
            f"MOCK copying data project {src_prj['uuid']} -> {dst_prj['uuid']} "
            f"with {len(nodes_map)} s3 objects by user={user_id}"
        )

        yield LRTask(TaskProgress(message="pytest mocked fct, started"))

        async def _mock_result():
            return None

        yield LRTask(
            TaskProgress(message="pytest mocked fct, finished", percent=1.0),
            _result=_mock_result(),
        )

    mock = mocker.patch(
        "simcore_service_webserver.projects.projects_handlers_crud.copy_data_folders_from_project",
        autospec=True,
        side_effect=_mock_copy_data_from_project,
    )

    async_mock = mocker.AsyncMock(return_value="")
    mock1 = mocker.patch(
        "simcore_service_webserver.projects._delete.delete_data_folders_of_project",
        side_effect=async_mock,
    )

    mock3 = mocker.patch(
        "simcore_service_webserver.projects.projects_handlers_crud.get_project_total_size",
        autospec=True,
        return_value=parse_obj_as(ByteSize, "1Gib"),
    )

    return MockedStorageSubsystem(mock, mock1, mock3)


@pytest.fixture
def asyncpg_storage_system_mock(mocker):
    mocked_method = mocker.patch(
        "simcore_service_webserver.login.storage.AsyncpgStorage.delete_user",
        return_value="",
    )
    return mocked_method


@pytest.fixture
async def mocked_director_v2_api(mocker) -> dict[str, MagicMock]:
    mock = {}

    #
    # NOTE: depending on the test, function might have to be patched
    #  via the director_v2_api or director_v2_core_dynamic_services modules
    #
    for func_name in (
        "get_dynamic_service_state",
        "get_dynamic_services",
        "run_dynamic_service",
        "stop_dynamic_service",
    ):
        for mod_name in ("director_v2_api", "director_v2_core_dynamic_services"):
            name = f"{mod_name}.{func_name}"
            mock[name] = mocker.patch(
                f"simcore_service_webserver.{name}",
                autospec=True,
                return_value={},
            )

    return mock


@pytest.fixture
def create_dynamic_service_mock(
    client: TestClient, mocked_director_v2_api: dict
) -> Callable:
    services = []

    async def create(user_id, project_id) -> dict:
        SERVICE_UUID = str(uuid4())
        SERVICE_KEY = "simcore/services/dynamic/3d-viewer"
        SERVICE_VERSION = "1.4.2"
        assert client.app
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
        mocked_director_v2_api[
            "director_v2_api.get_dynamic_services"
        ].return_value = services
        mocked_director_v2_api[
            "director_v2_core_dynamic_services.get_dynamic_services"
        ].return_value = services
        return running_service_dict

    return create


# POSTGRES CORE SERVICE ---------------------------------------------------


@pytest.fixture(scope="session")
def postgres_dsn(docker_services, docker_ip, default_app_cfg: dict) -> dict:
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


@pytest.fixture(scope="function")
def postgres_db(
    postgres_dsn: dict, postgres_service: str
) -> Iterator[sa.engine.Engine]:
    # Overrides packages/pytest-simcore/src/pytest_simcore/postgres_service.py::postgres_db to reduce scope
    url = postgres_service

    # Configures db and initializes tables
    kwargs = postgres_dsn.copy()
    assert pg_cli.discover.callback
    pg_cli.discover.callback(**kwargs)
    assert pg_cli.upgrade.callback
    pg_cli.upgrade.callback("head")
    # Uses syncrounous engine for that
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")

    yield engine

    assert pg_cli.downgrade.callback
    pg_cli.downgrade.callback("base")
    assert pg_cli.clean.callback
    pg_cli.clean.callback()

    orm.metadata.drop_all(engine)
    engine.dispose()


# REDIS CORE SERVICE ------------------------------------------------------


@pytest.fixture(scope="session")
def redis_service(docker_services, docker_ip) -> RedisSettings:
    # WARNING: overrides pytest_simcore.redis_service.redis_server function-scoped fixture!

    host = docker_ip
    port = docker_services.port_for("redis", 6379)
    redis_settings = RedisSettings(REDIS_HOST=docker_ip, REDIS_PORT=port)

    docker_services.wait_until_responsive(
        check=lambda: _is_redis_responsive(host, port),
        timeout=30.0,
        pause=0.1,
    )
    return redis_settings


@pytest.fixture
async def redis_client(redis_service: RedisSettings):
    client = aioredis.from_url(
        redis_service.dsn_resources, encoding="utf-8", decode_responses=True
    )
    yield client

    await client.flushall()
    await client.close(close_connection_pool=True)


@pytest.fixture
async def redis_locks_client(
    redis_service: RedisSettings,
) -> AsyncIterator[aioredis.Redis]:
    """Creates a redis client to communicate with a redis service ready"""
    client = aioredis.from_url(
        redis_service.dsn_locks, encoding="utf-8", decode_responses=True
    )

    yield client

    await client.flushall()
    await client.close(close_connection_pool=True)


def _is_redis_responsive(host: str, port: int) -> bool:
    r = redis.Redis(host=host, port=port)
    return r.ping() == True


# SOCKETS FIXTURES  --------------------------------------------------------

# Moved to packages/pytest-simcore/src/pytest_simcore/websocket_client.py


# USER GROUP FIXTURES -------------------------------------------------------


@pytest.fixture
async def primary_group(client, logged_user) -> dict[str, str]:
    primary_group, _, _ = await list_user_groups(client.app, logged_user["id"])
    return primary_group


@pytest.fixture
async def standard_groups(
    client, logged_user: dict
) -> AsyncIterator[list[dict[str, str]]]:
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
async def all_group(client, logged_user) -> dict[str, str]:
    _, _, all_group = await list_user_groups(client.app, logged_user["id"])
    return all_group


# GENERIC HELPER FUNCTIONS ----------------------------------------------------


def _patch_compose_mail(monkeypatch):
    async def print_mail_to_stdout(*args):
        _app, recipient, subject, body = args
        print(f"=== EMAIL TO: {recipient}\n=== SUBJECT: {subject}\n=== BODY:\n{body}")

    monkeypatch.setattr(
        simcore_service_webserver.login.utils, "compose_mail", print_mail_to_stdout
    )


def _is_postgres_responsive(url):
    """Check if something responds to ``url``"""
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True
