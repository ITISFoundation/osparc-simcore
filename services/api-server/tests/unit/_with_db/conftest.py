# pylint: disable=no-name-in-module
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
import shutil
import subprocess
import sys
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from pathlib import Path

import aiopg.sa
import aiopg.sa.engine as aiopg_sa_engine
import httpx
import pytest
import simcore_postgres_database.cli as pg_cli
import sqlalchemy as sa
import sqlalchemy.engine as sa_engine
import yaml
from aiopg.sa.connection import SAConnection
from fastapi import FastAPI
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from pydantic import PositiveInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers.faker_factories import (
    random_api_key,
    random_product,
    random_user,
)
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.api_keys import api_keys
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import PostgresSettings

## POSTGRES -----


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def docker_compose_file(
    default_app_env_vars: dict[str, str], tmpdir_factory: Callable
) -> Path:
    # Overrides fixture in https://github.com/avast/pytest-docker

    # NOTE: do not forget to add the current environ here, otherwise docker compose fails
    environ = dict(os.environ)
    environ.update(default_app_env_vars)

    src_path = CURRENT_DIR / "data" / "docker-compose.yml"
    assert src_path.exists

    dst_path = Path(str(tmpdir_factory.mktemp("config").join("docker-compose.yml")))

    shutil.copy(src_path, dst_path.parent)
    assert dst_path.exists()

    # configs
    subprocess.run(
        f'docker compose --file "{src_path}" config > "{dst_path}"',
        shell=True,  # noqa: S602
        check=True,
        env=environ,
    )

    return dst_path


@pytest.fixture(scope="session")
def postgres_service(docker_services, docker_ip, docker_compose_file: Path) -> dict:
    # check docker-compose's environ is resolved properly
    config = yaml.safe_load(docker_compose_file.read_text())
    environ = config["services"]["postgres"]["environment"]

    # builds DSN
    config = {
        "user": environ["POSTGRES_USER"],
        "password": environ["POSTGRES_PASSWORD"],
        "host": docker_ip,
        "port": docker_services.port_for("postgres", 5432),
        "database": environ["POSTGRES_DB"],
    }

    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(**config)

    def _create_checker() -> Callable:
        def is_postgres_responsive() -> bool:
            try:
                engine = sa.create_engine(dsn)
                conn = engine.connect()
                conn.close()
            except sa.exc.OperationalError:
                return False
            return True

        return is_postgres_responsive

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=_create_checker(),
        timeout=30.0,
        pause=0.1,
    )

    config["dsn"] = dsn
    return config


@pytest.fixture(scope="session")
def make_engine(postgres_service: dict) -> Callable:
    dsn = postgres_service["dsn"]  # session scope freezes dsn

    def maker(*, is_async=True) -> aiopg_sa_engine.Engine | sa_engine.Engine:
        if is_async:
            return aiopg.sa.create_engine(dsn)
        return sa.create_engine(dsn)

    return maker


@pytest.fixture
def migrated_db(postgres_service: dict, make_engine: Callable):
    # NOTE: this is equivalent to packages/pytest-simcore/src/pytest_simcore/postgres_service.py::postgres_db
    # but we do override postgres_dsn -> postgres_engine -> postgres_db because we want the latter
    # fixture to have local scope
    #
    kwargs = postgres_service.copy()
    kwargs.pop("dsn")
    pg_cli.discover.callback(**kwargs)
    pg_cli.upgrade.callback("head")

    yield

    pg_cli.downgrade.callback("base")
    pg_cli.clean.callback()
    # FIXME: deletes all because downgrade is not reliable!
    engine = make_engine(is_async=False)
    metadata.drop_all(engine)


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    default_app_env_vars: EnvVarsDict,
    mocker: MockerFixture,
) -> EnvVarsDict:
    """app environments WITH database settings"""
    mocker.patch("simcore_service_api_server.core.application.setup_rabbitmq")
    mocker.patch(
        "simcore_service_api_server.core._prometheus_instrumentation.setup_prometheus_instrumentation"
    )

    envs = setenvs_from_dict(monkeypatch, default_app_env_vars)
    assert "API_SERVER_POSTGRES" not in envs

    # Should be sufficient to create settings
    print(PostgresSettings.create_from_envs().model_dump_json(indent=1))

    return envs


@pytest.fixture
def app(app_environment: EnvVarsDict, migrated_db: None) -> FastAPI:
    """Overrides app to ensure that:
    - it uses default environ as pg
    - db is started and initialized
    """
    return init_app()


@pytest.fixture
async def connection(app: FastAPI) -> AsyncIterator[SAConnection]:
    assert app.state.engine
    async with app.state.engine.acquire() as conn:
        yield conn


@pytest.fixture
async def create_user_ids(
    connection: SAConnection,
) -> AsyncGenerator[Callable[[PositiveInt], AsyncGenerator[PositiveInt, None]], None]:
    async def _generate_user_ids(n: PositiveInt) -> AsyncGenerator[PositiveInt, None]:
        for _ in range(n):
            while True:
                user = random_user()
                result = await connection.execute(
                    users.select().where(users.c.name == user["name"])
                )
                entry = await result.first()
                if entry is None:
                    break
            uid = await connection.scalar(
                users.insert().values(user).returning(users.c.id)
            )
            assert uid
            _generate_user_ids.generated_ids.append(uid)
            yield uid

    _generate_user_ids.generated_ids = []
    yield _generate_user_ids

    for uid in _generate_user_ids.generated_ids:
        await connection.execute(users.delete().where(users.c.id == uid))


@pytest.fixture
async def create_product_names(
    connection: SAConnection,
) -> AsyncGenerator[Callable[[PositiveInt], AsyncGenerator[str, None]], None]:
    async def _generate_product_names(
        n: PositiveInt,
    ) -> AsyncGenerator[str, None]:
        for _ in range(n):
            while True:
                product = random_product(group_id=None)
                result = await connection.execute(
                    products.select().where(products.c.name == product["name"])
                )
                entry = await result.first()
                if entry is None:
                    break
            name = await connection.scalar(
                products.insert().values(product).returning(products.c.name)
            )
            assert name
            _generate_product_names.generated_names.append(name)
            yield name

    _generate_product_names.generated_names = []
    yield _generate_product_names

    for name in _generate_product_names.generated_names:
        await connection.execute(products.delete().where(products.c.name == name))


@pytest.fixture
async def create_fake_api_keys(
    connection: SAConnection,
    create_user_ids: Callable[[PositiveInt], AsyncGenerator[PositiveInt, None]],
    create_product_names: Callable[[PositiveInt], AsyncGenerator[str, None]],
) -> AsyncGenerator[Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]], None]:
    async def _generate_fake_api_key(n: PositiveInt):
        users = create_user_ids(n)
        products = create_product_names(n)
        for _ in range(n):
            product = await anext(products)
            user = await anext(users)
            result = await connection.execute(
                api_keys.insert()
                .values(**random_api_key(product, user))
                .returning(sa.literal_column("*"))
            )
            row = await result.fetchone()
            assert row
            _generate_fake_api_key.row_ids.append(row.id)
            yield ApiKeyInDB.model_validate(row)

    _generate_fake_api_key.row_ids = []
    yield _generate_fake_api_key

    for row_id in _generate_fake_api_key.row_ids:
        await connection.execute(api_keys.delete().where(api_keys.c.id == row_id))


@pytest.fixture
async def auth(
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]]
) -> httpx.BasicAuth:
    """overrides auth and uses access to real repositories instead of mocks"""
    async for key in create_fake_api_keys(1):
        return httpx.BasicAuth(key.api_key, key.api_secret)
    pytest.fail("Did not generate authentication")
