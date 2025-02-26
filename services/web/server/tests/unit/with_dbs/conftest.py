""" Configuration for unit testing with a postgress fixture

    - Unit testing of webserver app with a postgress service as fixture
    - Starts test session by running a postgres container as a fixture (see postgress_service)

    IMPORTANT: remember that these are still unit-tests!
"""

# nopycln: file
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import random
import sys
import textwrap
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Iterator
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import aiopg.sa
import pytest
import redis
import redis.asyncio as aioredis
import simcore_postgres_database.cli as pg_cli
import simcore_service_webserver.email
import simcore_service_webserver.email._core
import simcore_service_webserver.utils
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from aiopg.sa import create_engine
from aiopg.sa.connection import SAConnection
from faker import Faker
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.products import ProductName
from models_library.services_enums import ServiceState
from pydantic import ByteSize, TypeAdapter
from pytest_docker.plugin import Services
from pytest_mock import MockerFixture
from pytest_simcore.helpers import postgres_tools
from pytest_simcore.helpers.faker_factories import random_product
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import MockedStorageSubsystem
from pytest_simcore.helpers.webserver_projects import NewProject
from redis import Redis
from servicelib.aiohttp.application_keys import APP_AIOPG_ENGINE_KEY
from servicelib.aiohttp.long_running_tasks.client import LRTask
from servicelib.aiohttp.long_running_tasks.server import ProgressPercent, TaskProgress
from servicelib.common_aiopg_utils import DSN
from settings_library.email import SMTPSettings
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_postgres_database.models.groups_extra_properties import (
    groups_extra_properties,
)
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.products_prices import products_prices
from simcore_postgres_database.utils_products import (
    get_default_product_name,
    get_or_create_product_group,
)
from simcore_service_webserver._constants import INDEX_RESOURCE_NAME
from simcore_service_webserver.application import create_application
from simcore_service_webserver.application_settings_utils import AppConfigDict
from simcore_service_webserver.db.plugin import get_database_engine
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.statics._constants import (
    FRONTEND_APP_DEFAULT,
    FRONTEND_APPS_AVAILABLE,
)
from sqlalchemy import exc as sql_exceptions

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# DEPLOYED SERVICES FOR TESTSUITE SESSION -----------------------------------


@pytest.fixture(autouse=True)
def disable_swagger_doc_generation(
    monkeypatch: pytest.MonkeyPatch, osparc_simcore_root_dir: Path
):
    """
    by not enabling the swagger documentation, 1.8s per test is gained
    """
    monkeypatch.setenv("REST_SWAGGER_API_DOC_ENABLED", "0")
    monkeypatch.setenv("WEBSERVER_GARBAGE_COLLECTOR", "null")


@pytest.fixture(scope="session")
def docker_compose_env(default_app_cfg: AppConfigDict) -> Iterator[pytest.MonkeyPatch]:
    postgres_cfg = default_app_cfg["db"]["postgres"]
    redis_cfg = default_app_cfg["resource_manager"]["redis"]

    # docker-compose reads these environs
    with pytest.MonkeyPatch().context() as patcher:
        patcher.setenv("TEST_POSTGRES_DB", postgres_cfg["database"])
        patcher.setenv("TEST_POSTGRES_USER", postgres_cfg["user"])
        patcher.setenv("TEST_POSTGRES_PASSWORD", postgres_cfg["password"])
        # Redis
        patcher.setenv("TEST_REDIS_PASSWORD", redis_cfg["password"])
        yield patcher


@pytest.fixture(scope="session")
def docker_compose_file(docker_compose_env: pytest.MonkeyPatch) -> str:
    """Overrides pytest-docker fixture"""
    compose_path = CURRENT_DIR / "docker-compose-devel.yml"
    assert compose_path.exists()
    return f"{compose_path}"


# WEB SERVER/CLIENT FIXTURES ------------------------------------------------


@pytest.fixture
def webserver_test_server_port(unused_tcp_port_factory: Callable):
    # used to create a TestServer that emulates web-server service
    return unused_tcp_port_factory()


@pytest.fixture
def storage_test_server_port(
    unused_tcp_port_factory: Callable, webserver_test_server_port: int
):
    # used to create a TestServer that emulates storage service
    port = unused_tcp_port_factory()
    assert port != webserver_test_server_port
    return port


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    default_app_cfg: AppConfigDict,
    mock_env_devel_environment: EnvVarsDict,
    storage_test_server_port: int,
    monkeypatch_setenv_from_app_config: Callable[[AppConfigDict], EnvVarsDict],
) -> EnvVarsDict:
    # WARNING: this fixture is commonly overriden. Check before renaming.
    """overridable fixture that defines the ENV for the webserver application
    based on legacy application config files.

    override like so:
    @pytest.fixture
    def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
        monkeypatch.setenv("MODIFIED_ENV", "VALUE")
        return app_environment | {"MODIFIED_ENV":"VALUE"}
    """
    # NOTE: remains from from old cfg
    cfg = deepcopy(default_app_cfg)
    cfg["storage"]["port"] = storage_test_server_port
    envs_app_cfg = monkeypatch_setenv_from_app_config(cfg)

    return (
        mock_env_devel_environment
        | envs_app_cfg
        | setenvs_from_dict(
            monkeypatch,
            {
                # this emulates hostname: "wb-{{.Node.Hostname}}-{{.Task.Slot}}" in docker-compose that
                # affects PostgresSettings.POSTGRES_CLIENT_NAME
                "HOSTNAME": "wb-test_host.0"
            },
        )
    )


@pytest.fixture
def mocked_send_email(monkeypatch: pytest.MonkeyPatch) -> None:
    # WARNING: this fixture is commonly overriden. Check before renaming.
    async def _print_mail_to_stdout(
        settings: SMTPSettings,
        *,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        **kwargs,
    ):
        print(
            f"=== EMAIL FROM: {sender}\n",
            f"=== EMAIL TO: {recipient}\n",
            f"=== SUBJECT: {subject}\n",
            f"=== BODY:\n{body}\n",
            f"=== EXTRA:\n{kwargs}",
        )

    # pylint: disable=protected-access
    monkeypatch.setattr(
        simcore_service_webserver.email._core,  # noqa: SLF001
        "_send_email",
        _print_mail_to_stdout,
    )


@pytest.fixture
def web_server(
    event_loop: asyncio.AbstractEventLoop,
    app_environment: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    webserver_test_server_port: int,
    # tools
    aiohttp_server: Callable,
    mocked_send_email: None,
    disable_static_webserver: Callable,
) -> TestServer:
    assert app_environment

    # original APP
    app = create_application()

    disable_static_webserver(app)

    server = event_loop.run_until_complete(
        aiohttp_server(app, port=webserver_test_server_port)
    )

    assert isinstance(postgres_db, sa.engine.Engine)

    pg_settings = dict(e.split("=") for e in app[APP_AIOPG_ENGINE_KEY].dsn.split())
    assert pg_settings["host"] == postgres_db.url.host
    assert int(pg_settings["port"]) == postgres_db.url.port
    assert pg_settings["user"] == postgres_db.url.username

    return server


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    web_server: TestServer,
    mock_orphaned_services,
    redis_client: Redis,
) -> TestClient:
    """
    Deployed web-server + postgres + redis services
    client connect to web-server
    """
    # WARNING: this fixture is commonly overriden. Check before renaming.
    return event_loop.run_until_complete(aiohttp_client(web_server))


@pytest.fixture(scope="session")
def osparc_product_name() -> str:
    return "osparc"


@pytest.fixture
async def default_product_name(client: TestClient) -> ProductName:
    assert client.app
    async with get_database_engine(client.app).acquire() as conn:
        return await get_default_product_name(conn)


# SUBSYSTEM MOCKS FIXTURES ------------------------------------------------
#
# Mocks entirely or part of the calls to the web-server subsystems
#


@pytest.fixture
def catalog_subsystem_mock(
    mocker: MockerFixture,
) -> Iterator[Callable[[list[ProjectDict]], None]]:
    """
    Patches some API calls in the catalog plugin
    """
    services_in_project = []

    def _creator(projects: list[ProjectDict]) -> None:
        for proj in projects or []:
            services_in_project.extend(
                [
                    {"key": s["key"], "version": s["version"]}
                    for _, s in proj["workbench"].items()
                ]
            )

    async def _mocked_get_services_for_user(*args, **kwargs):
        return services_in_project

    for namespace in (
        "simcore_service_webserver.projects._projects_service_read.get_services_for_user_in_product",
        "simcore_service_webserver.projects._crud_handlers.get_services_for_user_in_product",
    ):
        mock = mocker.patch(
            namespace,
            autospec=True,
        )

        mock.side_effect = _mocked_get_services_for_user

    yield _creator

    services_in_project.clear()


@pytest.fixture
def disable_static_webserver(monkeypatch: pytest.MonkeyPatch) -> Callable:
    """
    Disables the static-webserver module
    Avoids fecthing and caching index.html pages
    Mocking a response for all the services which expect it
    """

    async def fake_front_end_handler(request: web.Request) -> web.Response:
        """
        Emulates the reply of the '/' path when the static-webserver is disabled
        """
        html = textwrap.dedent(
            f"""\
            <!DOCTYPE html>
            <html>
            <body>
                <h1>OSPARC-SIMCORE</h1>
                    <p> This is a result of disable_static_webserver fixture for product OSPARC ({__name__})</p>
                <h2>Request info</h2>
                    <ul>
                        <li>{request.url=}</li>
                        <li>{request.headers=}</li>
                        <li>{request.content_length=}</li>
                    </ul>
            </body>
            </html>
            """
        )
        return web.Response(text=html)

    # mount and serve some staic mocked content
    monkeypatch.setenv("WEBSERVER_STATICWEB", "null")

    def add_index_route(app: web.Application) -> None:
        app.router.add_get("/", fake_front_end_handler, name=INDEX_RESOURCE_NAME)

    return add_index_route


@pytest.fixture
async def storage_subsystem_mock(mocker: MockerFixture) -> MockedStorageSubsystem:
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
            TaskProgress(
                message="pytest mocked fct, finished", percent=ProgressPercent(1.0)
            ),
            _result=_mock_result(),
        )

    mock = mocker.patch(
        "simcore_service_webserver.projects._projects_service_create.copy_data_folders_from_project",
        autospec=True,
        side_effect=_mock_copy_data_from_project,
    )

    async_mock = mocker.AsyncMock(return_value="")
    mock1 = mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.delete_data_folders_of_project",
        autospec=True,
        side_effect=async_mock,
    )

    mock2 = mocker.patch(
        "simcore_service_webserver.projects.projects_service.storage_api.delete_data_folders_of_project_node",
        autospec=True,
        return_value=None,
    )

    mock3 = mocker.patch(
        "simcore_service_webserver.projects._projects_service_create.get_project_total_size_simcore_s3",
        autospec=True,
        return_value=TypeAdapter(ByteSize).validate_python("1Gib"),
    )

    return MockedStorageSubsystem(mock, mock1, mock2, mock3)


@pytest.fixture
def asyncpg_storage_system_mock(mocker):
    return mocker.patch(
        "simcore_service_webserver.login.storage.AsyncpgStorage.delete_user",
        return_value="",
    )


@pytest.fixture
async def mocked_dynamic_services_interface(
    mocker: MockerFixture,
) -> dict[str, MagicMock]:
    mock = {}

    for func_name in (
        "list_dynamic_services",
        "get_dynamic_service",
        "run_dynamic_service",
        "stop_dynamic_service",
    ):
        name = f"dynamic_scheduler.api.{func_name}"
        mock[name] = mocker.patch(
            f"simcore_service_webserver.{name}",
            autospec=True,
            return_value={},
        )

    mock["director_v2.api.create_or_update_pipeline"] = mocker.patch(
        "simcore_service_webserver.director_v2.api.create_or_update_pipeline",
        autospec=True,
        return_value=None,
    )
    return mock


@pytest.fixture
def create_dynamic_service_mock(
    client: TestClient, mocked_dynamic_services_interface: dict, faker: Faker
) -> Callable[..., Awaitable[DynamicServiceGet]]:
    services = []

    async def _create(**service_override_kwargs) -> DynamicServiceGet:
        SERVICE_KEY = "simcore/services/dynamic/3d-viewer"
        SERVICE_VERSION = "1.4.2"
        assert client.app

        service_config = {
            "published_port": faker.pyint(min_value=3000, max_value=60000),
            "service_uuid": faker.uuid4(cast_to=None),
            "service_key": SERVICE_KEY,
            "service_version": SERVICE_VERSION,
            "service_host": faker.url(),
            "service_port": faker.pyint(min_value=3000, max_value=60000),
            "service_state": random.choice(list(ServiceState)),  # noqa: S311
            "user_id": faker.pyint(min_value=1),
            "project_id": faker.uuid4(cast_to=None),
        } | service_override_kwargs

        running_service = DynamicServiceGet(**service_config)

        services.append(running_service)
        # reset the future or an invalidStateError will appear as set_result sets the future to done
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.list_dynamic_services"
        ].return_value = services

        return running_service

    return _create


def _is_postgres_responsive(url: str):
    """Check if something responds to url"""
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sql_exceptions.OperationalError:
        return False
    return True


@pytest.fixture(scope="session")
def postgres_dsn(
    docker_services: Services, docker_ip: str | Any, default_app_cfg: dict
) -> dict:
    cfg = deepcopy(default_app_cfg["db"]["postgres"])
    cfg["host"] = docker_ip
    cfg["port"] = docker_services.port_for("postgres", 5432)
    return cfg


@pytest.fixture(scope="session")
def postgres_service(docker_services: Services, postgres_dsn: dict) -> str:
    url = DSN.format(**postgres_dsn)

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: _is_postgres_responsive(url),
        timeout=30.0,
        pause=0.1,
    )

    return url


@pytest.fixture(scope="module")
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
    sync_engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")

    yield sync_engine

    try:
        # NOTE: we directly drop the table, that is faster
        # testing the upgrade/downgrade is already done in postgres-database.
        # there is no need to it here.
        postgres_tools.force_drop_all_tables(sync_engine)
    finally:
        sync_engine.dispose()


@pytest.fixture
async def aiopg_engine(postgres_db: sa.engine.Engine) -> AsyncIterator[aiopg.sa.Engine]:
    engine = await create_engine(f"{postgres_db.url}")
    assert engine

    yield engine

    if engine:
        engine.close()
        await engine.wait_closed()


# REDIS CORE SERVICE ------------------------------------------------------
def _is_redis_responsive(host: str, port: int, password: str) -> bool:
    # username via https://stackoverflow.com/a/78236235
    r = redis.Redis(host=host, username="default", port=port, password=password)
    return r.ping() is True


@pytest.fixture(scope="session")
def redis_service(docker_services, docker_ip, default_app_cfg: dict) -> RedisSettings:
    # WARNING: overrides pytest_simcore.redis_service.redis_server function-scoped fixture!

    host = docker_ip
    port = docker_services.port_for("redis", 6379)
    password = default_app_cfg["resource_manager"]["redis"]["password"]
    redis_settings = RedisSettings(
        REDIS_HOST=docker_ip, REDIS_PORT=port, REDIS_PASSWORD=password
    )

    docker_services.wait_until_responsive(
        check=lambda: _is_redis_responsive(host, port, password),
        timeout=30.0,
        pause=0.1,
    )
    return redis_settings


@pytest.fixture
async def redis_client(redis_service: RedisSettings) -> AsyncIterator[aioredis.Redis]:
    client = aioredis.from_url(
        redis_service.build_redis_dsn(RedisDatabase.RESOURCES),
        encoding="utf-8",
        decode_responses=True,
    )
    yield client

    await client.flushall()
    await client.aclose(close_connection_pool=True)  # type: ignore[attr-defined]


@pytest.fixture
async def redis_locks_client(
    redis_service: RedisSettings,
) -> AsyncIterator[aioredis.Redis]:
    """Creates a redis client to communicate with a redis service ready"""
    client = aioredis.from_url(
        redis_service.build_redis_dsn(RedisDatabase.LOCKS),
        encoding="utf-8",
        decode_responses=True,
    )

    yield client

    await client.flushall()
    await client.aclose(close_connection_pool=True)


# SOCKETS FIXTURES  --------------------------------------------------------
# Moved to packages/pytest-simcore/src/pytest_simcore/websocket_client.py


@pytest.fixture
def mock_dynamic_scheduler_rabbitmq(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_webserver.dynamic_scheduler.api.get_rabbitmq_client",
        autospec=True,
        return_value=AsyncMock(),
    )


@pytest.fixture
def mocked_notifications_plugin(mocker: MockerFixture) -> dict[str, mock.Mock]:
    mocked_subscribe = mocker.patch(
        "simcore_service_webserver.notifications.project_logs.subscribe",
        autospec=True,
    )
    mocked_unsubscribe = mocker.patch(
        "simcore_service_webserver.notifications.project_logs.unsubscribe",
        autospec=True,
    )

    return {"subscribe": mocked_subscribe, "unsubscribe": mocked_unsubscribe}


@pytest.fixture
async def user_project(
    client: TestClient,
    fake_project: ProjectDict,
    logged_user: UserInfoDict,
    tests_data_dir: Path,
    osparc_product_name: ProductName,
) -> AsyncIterator[ProjectDict]:
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def with_permitted_override_services_specifications(
    aiopg_engine: aiopg.sa.engine.Engine,
) -> AsyncIterator[None]:
    old_value = False
    async with aiopg_engine.acquire() as conn:
        old_value = bool(
            await conn.scalar(
                sa.select(
                    groups_extra_properties.c.override_services_specifications
                ).where(groups_extra_properties.c.group_id == 1)
            )
        )

        await conn.execute(
            groups_extra_properties.update()
            .where(groups_extra_properties.c.group_id == 1)
            .values(override_services_specifications=True)
        )

    yield

    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            groups_extra_properties.update()
            .where(groups_extra_properties.c.group_id == 1)
            .values(override_services_specifications=old_value)
        )


# PRODUCT PRICES FIXTURES -------------------------------------------------------


@pytest.fixture
async def _pre_connection(postgres_db: sa.engine.Engine) -> AsyncIterable[SAConnection]:
    # NOTE: call to postgres BEFORE app starts
    async with await create_engine(
        f"{postgres_db.url}"
    ) as engine, engine.acquire() as conn:
        yield conn


@pytest.fixture
async def all_products_names(
    _pre_connection: SAConnection,
) -> AsyncIterable[list[ProductName]]:
    # default product
    result = await _pre_connection.execute(
        products.select().order_by(products.c.priority)
    )
    rows = await result.fetchall()
    assert rows
    assert len(rows) == 1
    osparc_product_row = rows[0]
    assert osparc_product_row.name == FRONTEND_APP_DEFAULT
    assert osparc_product_row.priority == 0

    # creates remaing products for front-end
    priority = 1
    for name in FRONTEND_APPS_AVAILABLE:
        if name != FRONTEND_APP_DEFAULT:
            result = await _pre_connection.execute(
                products.insert().values(
                    random_product(
                        name=name,
                        priority=priority,
                        login_settings=osparc_product_row.login_settings,
                        group_id=None,
                    )
                )
            )
            await get_or_create_product_group(_pre_connection, product_name=name)
            priority += 1

    # get all products
    result = await _pre_connection.execute(
        sa.select(products.c.name).order_by(products.c.priority)
    )
    rows = await result.fetchall()

    yield [r.name for r in rows]

    await _pre_connection.execute(products_prices.delete())
    await _pre_connection.execute(
        products.delete().where(products.c.name != FRONTEND_APP_DEFAULT)
    )


@pytest.fixture
async def all_product_prices(
    _pre_connection: SAConnection,
    all_products_names: list[ProductName],
    faker: Faker,
) -> dict[ProductName, Decimal | None]:
    """Initial list of prices for all products"""

    # initial list of prices
    product_price = {
        "osparc": Decimal(0),  # free of charge
        "tis": Decimal(5),
        "tiplite": Decimal(5),
        "s4l": Decimal(9),
        "s4llite": Decimal(0),  # free of charge
        "s4lacad": Decimal(1.1),
    }

    result = {}
    for product_name in all_products_names:
        usd_or_none = product_price.get(product_name)
        if usd_or_none is not None:
            await _pre_connection.execute(
                products_prices.insert().values(
                    product_name=product_name,
                    usd_per_credit=usd_or_none,
                    comment=faker.sentence(),
                    min_payment_amount_usd=10,
                    stripe_price_id=faker.pystr(),
                    stripe_tax_rate_id=faker.pystr(),
                )
            )

        result[product_name] = usd_or_none

    return result


@pytest.fixture
async def latest_osparc_price(
    all_product_prices: dict[ProductName, Decimal],
    _pre_connection: SAConnection,
) -> Decimal:
    """This inserts a new price for osparc in the history
    (i.e. the old price of osparc is still in the database)
    """

    usd = await _pre_connection.scalar(
        products_prices.insert()
        .values(
            product_name="osparc",
            usd_per_credit=all_product_prices["osparc"] + 5,
            comment="New price for osparc",
            stripe_price_id="stripe-price-id",
            stripe_tax_rate_id="stripe-tax-rate-id",
        )
        .returning(products_prices.c.usd_per_credit)
    )
    assert usd is not None
    assert usd != all_product_prices["osparc"]
    return Decimal(usd)
