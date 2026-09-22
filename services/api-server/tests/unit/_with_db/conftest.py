# pylint: disable=no-name-in-module
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncGenerator, Callable

import httpx
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from pydantic import PositiveInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers.faker_factories import (
    random_api_auth,
    random_product,
    random_user,
)
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.db_asyncpg_engine import get_engine
from simcore_postgres_database.models.api_keys import api_keys
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users
from simcore_service_api_server.core.application import create_app
from simcore_service_api_server.core.settings import PostgresSettings
from sqlalchemy.ext.asyncio import AsyncEngine

## POSTGRES -----


@pytest.fixture
def migrated_db(
    postgres_db_per_test_from_template: sa.engine.Engine,
) -> None:
    # NOTE: this is equivalent to packages/pytest-simcore/src/pytest_simcore/postgres_service.py::postgres_db
    # (fresh migrated schema before every test), but instead of running alembic
    # 'upgrade head'/'downgrade base' for every test, the database is re-cloned from a
    # session-scoped migrated template
    assert postgres_db_per_test_from_template is not None


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    default_app_env_vars: EnvVarsDict,
    mocker: MockerFixture,
) -> EnvVarsDict:
    """app environments WITH database settings"""
    mocker.patch("simcore_service_api_server.core.application.configure_rabbitmq")
    mocker.patch("simcore_service_api_server.core.application.configure_api_server_prometheus_instrumentation")

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
) -> AsyncGenerator[Callable[[PositiveInt], AsyncGenerator[PositiveInt]]]:
    async def _generate_user_ids(n: PositiveInt) -> AsyncGenerator[PositiveInt]:
        for _ in range(n):
            while True:
                user = random_user()
                async with async_engine.connect() as conn:
                    result = await conn.execute(users.select().where(users.c.name == user["name"]))
                    entry = result.one_or_none()
                    if entry is None:
                        break

            async with async_engine.begin() as conn:
                uid = await conn.scalar(users.insert().values(user).returning(users.c.id))
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
) -> AsyncGenerator[Callable[[PositiveInt], AsyncGenerator[str]]]:
    async def _generate_product_names(
        n: PositiveInt,
    ) -> AsyncGenerator[str]:
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
                name = await conn.scalar(products.insert().values(product).returning(products.c.name))

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
    create_user_ids: Callable[[PositiveInt], AsyncGenerator[PositiveInt]],
    create_product_names: Callable[[PositiveInt], AsyncGenerator[str]],
) -> AsyncGenerator[Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB]]]:
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
                        api_secret=sa.func.crypt(plain_api_secret, sa.func.gen_salt("bf", 10)),
                        **api_auth,
                    )
                    .returning(*returning_cols)
                )
                row = result.one()
                assert row

            _generate_fake_api_key.row_ids.append(row.id)

            yield ApiKeyInDB.model_validate({"api_secret": plain_api_secret, **row._asdict()})

    _generate_fake_api_key.row_ids = []
    yield _generate_fake_api_key

    async with async_engine.begin() as conn:
        await conn.execute(api_keys.delete().where(api_keys.c.id.in_(_generate_fake_api_key.row_ids)))


@pytest.fixture
async def auth(
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB]],
) -> httpx.BasicAuth:
    """overrides auth and uses access to real repositories instead of mocks"""
    async for key in create_fake_api_keys(1):
        return httpx.BasicAuth(key.api_key, key.api_secret)
    pytest.fail("Did not generate authentication")
