# pylint: disable=no-name-in-module
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from pprint import pformat

import aiopg.sa
import aiopg.sa.engine as aiopg_sa_engine
import httpx
import pytest
import simcore_postgres_database.cli as pg_cli
import simcore_service_api_server.db.tables as orm
import sqlalchemy as sa
import sqlalchemy.engine as sa_engine
import yaml
from aiopg.sa.result import RowProxy
from faker import Faker
from fastapi import FastAPI
from pytest import MonkeyPatch
from pytest_simcore.helpers.rawdata_fakers import random_user
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_postgres_database.models.base import metadata
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import PostgresSettings
from simcore_service_api_server.db.repositories import BaseRepository
from simcore_service_api_server.db.repositories.users import UsersRepository
from simcore_service_api_server.models.domain.api_keys import ApiKeyInDB

## POSTGRES -----


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def docker_compose_file(
    default_app_env_vars: dict[str, str], tmpdir_factory: Callable
) -> Path:
    # Overrides fixture in https://github.com/avast/pytest-docker

    # NOTE: do not forget to add the current environ here, otherwise docker-compose fails
    environ = dict(os.environ)
    environ.update(default_app_env_vars)

    src_path = CURRENT_DIR / "data" / "docker-compose.yml"
    assert src_path.exists

    dst_path = Path(str(tmpdir_factory.mktemp("config").join("docker-compose.yml")))

    shutil.copy(src_path, dst_path.parent)
    assert dst_path.exists()

    # configs
    subprocess.run(
        f'docker-compose --file "{src_path}" config > "{dst_path}"',
        shell=True,
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
    monkeypatch: MonkeyPatch, default_app_env_vars: EnvVarsDict
) -> EnvVarsDict:
    """app environments WITH database settings"""

    envs = setenvs_from_dict(monkeypatch, default_app_env_vars)
    assert "API_SERVER_POSTGRES" not in envs

    # Should be sufficient to create settings
    print(PostgresSettings.create_from_envs().json(indent=1))

    return envs


@pytest.fixture
def app(app_environment: EnvVarsDict, migrated_db: None) -> FastAPI:
    """Overrides app to ensure that:
    - it uses default environ as pg
    - db is started and initialized
    """
    return init_app()


## FAKE DATA injected at repositories interface ----------------------


class _ExtendedUsersRepository(UsersRepository):
    # pylint: disable=no-value-for-parameter

    async def create(self, **user) -> int:
        values = random_user(**user)
        async with self.db_engine.acquire() as conn:
            user_id = await conn.scalar(orm.users.insert().values(**values))

        print("Created user ", pformat(values), f"with user_id={user_id}")
        return user_id


class _ExtendedApiKeysRepository(BaseRepository):
    # pylint: disable=no-value-for-parameter

    async def create(self, name: str, *, api_key: str, api_secret: str, user_id: int):
        values = {
            "display_name": name,
            "user_id": user_id,
            "api_key": api_key,
            "api_secret": api_secret,
        }
        async with self.db_engine.acquire() as conn:
            _id = await conn.scalar(orm.api_keys.insert().values(**values))

            # check inserted
            row: RowProxy = await (
                await conn.execute(
                    orm.api_keys.select().where(orm.api_keys.c.id == _id)
                )
            ).first()

        return ApiKeyInDB.from_orm(row)


@pytest.fixture
async def fake_user_id(app: FastAPI, faker: Faker) -> int:
    # WARNING: created but not deleted upon tear-down, i.e. this is for one use!
    return await _ExtendedUsersRepository(app.state.engine).create(
        email=faker.email(),
        password=faker.password(),
        name=faker.user_name(),
    )


@pytest.fixture
async def fake_api_key(app: FastAPI, fake_user_id: int, faker: Faker) -> ApiKeyInDB:
    # WARNING: created but not deleted upon tear-down, i.e. this is for one use!
    return await _ExtendedApiKeysRepository(app.state.engine).create(
        "test-api-key",
        api_key=faker.word(),
        api_secret=faker.password(),
        user_id=fake_user_id,
    )


@pytest.fixture
def auth(fake_api_key: ApiKeyInDB) -> httpx.BasicAuth:
    """overrides auth and uses access to real repositories instead of mocks"""
    return httpx.BasicAuth(
        fake_api_key.api_key, fake_api_key.api_secret.get_secret_value()
    )
