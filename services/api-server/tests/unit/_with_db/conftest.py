# pylint: disable=no-name-in-module
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
import shutil
import subprocess
import sys
from collections.abc import AsyncGenerator, Callable, Iterable
from pathlib import Path
from typing import TypedDict

import httpx
import pytest
import simcore_postgres_database.cli as pg_cli
import sqlalchemy as sa
import sqlalchemy.engine
import yaml
from fastapi import FastAPI
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from pydantic import PositiveInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers import postgres_tools
from pytest_simcore.helpers.faker_factories import (
    random_api_auth,
    random_product,
    random_user,
)
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.api_keys import api_keys
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users
from simcore_service_api_server.clients.postgres import get_engine
from simcore_service_api_server.core.application import create_app
from simcore_service_api_server.core.settings import PostgresSettings
from sqlalchemy.ext.asyncio import AsyncEngine

## POSTGRES -----


_CURRENT_DIR = (
    Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
)


@pytest.fixture(scope="session")
def docker_compose_file(
    default_app_env_vars: dict[str, str], tmpdir_factory: Callable
) -> Path:
    # Overrides fixture in https://github.com/avast/pytest-docker

    # NOTE: do not forget to add the current environ here, otherwise docker compose fails
    environ = dict(os.environ)
    environ.update(default_app_env_vars)

    src_path = _CURRENT_DIR / "data" / "docker-compose.yml"
    assert src_path.exists

    dst_path = Path(str(tmpdir_factory.mktemp("config").join("docker-compose.yml")))

    shutil.copy(src_path, dst_path.parent)
    assert dst_path.exists()

    # configs
    subprocess.run(
        f'docker compose --file "{src_path}" config > "{dst_path}"',
        shell=True,
        check=True,
        env=environ,
    )

    return dst_path


class PostgreServiceInfoDict(TypedDict):
    dsn: str
    user: str
    password: str
    host: str
    port: int
    datbase: str


@pytest.fixture(scope="session")
def postgres_service(
    docker_services, docker_ip, docker_compose_file: Path
) -> PostgreServiceInfoDict:
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
    return PostgreServiceInfoDict(**config)


@pytest.fixture(scope="session")
def sync_engine(
    postgres_service: PostgreServiceInfoDict,
) -> Iterable[sqlalchemy.engine.Engine]:
    _engine: sqlalchemy.engine.Engine = sa.create_engine(url=postgres_service["dsn"])
    yield _engine
    _engine.dispose()


@pytest.fixture
def migrated_db(postgres_service: dict, sync_engine: sqlalchemy.engine.Engine):
    # NOTE: this is equivalent to packages/pytest-simcore/src/pytest_simcore/postgres_service.py::postgres_db
    # but we do override postgres_dsn -> postgres_engine -> postgres_db because we want the latter
    # fixture to have local scope
    #
    kwargs = postgres_service.copy()
    kwargs.pop("dsn")
    assert pg_cli.discover.callback is not None
    pg_cli.discover.callback(**kwargs)

    assert pg_cli.upgrade.callback is not None
    pg_cli.upgrade.callback("head")

    yield

    assert pg_cli.downgrade.callback is not None
    pg_cli.downgrade.callback("base")

    assert pg_cli.clean.callback is not None
    pg_cli.clean.callback()

    postgres_tools.force_drop_all_tables(sync_engine)


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

    envs = setenvs_from_dict(monkeypatch, {**default_app_env_vars})
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
    return create_app()


@pytest.fixture
async def async_engine(app: FastAPI) -> AsyncEngine:
    return get_engine(app)


@pytest.fixture
async def create_user_ids(
    async_engine: AsyncEngine,
) -> AsyncGenerator[Callable[[PositiveInt], AsyncGenerator[PositiveInt, None]], None]:
    async def _generate_user_ids(n: PositiveInt) -> AsyncGenerator[PositiveInt, None]:
        for _ in range(n):
            while True:
                user = random_user()
                async with async_engine.connect() as conn:
                    result = await conn.execute(
                        users.select().where(users.c.name == user["name"])
                    )
                    entry = result.one_or_none()
                    if entry is None:
                        break

            async with async_engine.begin() as conn:
                uid = await conn.scalar(
                    users.insert().values(user).returning(users.c.id)
                )
                assert uid

            _generate_user_ids.generated_ids.append(uid)

            yield uid

    _generate_user_ids.generated_ids = []

    yield _generate_user_ids

    for uid in _generate_user_ids.generated_ids:
        async with async_engine.begin() as conn:
            await conn.execute(users.delete().where(users.c.id == uid))


@pytest.fixture
async def create_product_names(
    async_engine: AsyncEngine,
) -> AsyncGenerator[Callable[[PositiveInt], AsyncGenerator[str, None]], None]:
    async def _generate_product_names(
        n: PositiveInt,
    ) -> AsyncGenerator[str, None]:
        for _ in range(n):
            while True:
                product = random_product(group_id=None)
                async with async_engine.connect() as conn:
                    result = await conn.execute(
                        products.select().where(products.c.name == product["name"]),
                    )
                    entry = result.one_or_none()
                    if entry is None:
                        break

            async with async_engine.begin() as conn:
                name = await conn.scalar(
                    products.insert().values(product).returning(products.c.name)
                )

            assert name
            _generate_product_names.generated_names.append(name)

            yield name

    _generate_product_names.generated_names = []
    yield _generate_product_names

    for name in _generate_product_names.generated_names:
        async with async_engine.begin() as conn:
            await conn.execute(products.delete().where(products.c.name == name))


@pytest.fixture
async def create_fake_api_keys(
    async_engine: AsyncEngine,
    create_user_ids: Callable[[PositiveInt], AsyncGenerator[PositiveInt, None]],
    create_product_names: Callable[[PositiveInt], AsyncGenerator[str, None]],
) -> AsyncGenerator[Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]], None]:

    async def _generate_fake_api_key(n: PositiveInt):
        users, products = create_user_ids(n), create_product_names(n)
        excluded_column = "api_secret"
        returning_cols = [col for col in api_keys.c if col.name != excluded_column]

        for _ in range(n):
            product = await anext(products)
            user = await anext(users)

            api_auth = random_api_auth(product, user)
            plain_api_secret = api_auth.pop("api_secret")

            async with async_engine.begin() as conn:
                result = await conn.execute(
                    api_keys.insert()
                    .values(
                        api_secret=sa.func.crypt(
                            plain_api_secret, sa.func.gen_salt("bf", 10)
                        ),
                        **api_auth,
                    )
                    .returning(*returning_cols)
                )
                row = result.one()
                assert row

            _generate_fake_api_key.row_ids.append(row.id)

            yield ApiKeyInDB.model_validate({"api_secret": plain_api_secret, **row})

    _generate_fake_api_key.row_ids = []
    yield _generate_fake_api_key

    async with async_engine.begin() as conn:
        await conn.execute(
            api_keys.delete().where(api_keys.c.id.in_(_generate_fake_api_key.row_ids))
        )


@pytest.fixture
async def auth(
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
) -> httpx.BasicAuth:
    """overrides auth and uses access to real repositories instead of mocks"""
    async for key in create_fake_api_keys(1):
        return httpx.BasicAuth(key.api_key, key.api_secret)
    pytest.fail("Did not generate authentication")
