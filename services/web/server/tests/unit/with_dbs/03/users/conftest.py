# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncGenerator, AsyncIterable, Callable
from typing import Any

import pytest
import pytest_asyncio
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestServer
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp.application import create_safe_application
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import get_asyncpg_engine, setup_db
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest_asyncio.fixture(loop_scope="function", scope="function")
async def web_server(
    app_environment: EnvVarsDict,  # configs
    postgres_db: sa.engine.Engine,  # db-ready
    webserver_test_server_port: int,
    aiohttp_server: Callable,
) -> TestServer:
    """Creates an app that setups the database only"""
    app = web.Application()

    app = create_safe_application()
    setup_settings(app)
    setup_db(app)

    return await aiohttp_server(app, port=webserver_test_server_port)


@pytest.fixture
def app(web_server: TestServer) -> web.Application:
    """Setup and started app with db"""
    _app = web_server.app
    assert get_asyncpg_engine(_app)
    return _app


@pytest.fixture
def asyncpg_engine(
    app: web.Application,
) -> AsyncEngine:
    """Returns the asyncpg engine ready to be used against postgres"""
    return get_asyncpg_engine(app)


@pytest.fixture
async def pre_registration_details_db_cleanup(
    app: web.Application,
) -> AsyncGenerator[None, None]:
    """Fixture to clean up all pre-registration details after test"""
    yield

    # Tear down - clean up the pre-registration details table
    async with get_asyncpg_engine(app).connect() as conn:
        await conn.execute(sa.delete(users_pre_registration_details))
        await conn.commit()


@pytest.fixture
async def product_owner_user(
    asyncpg_engine: AsyncEngine,
) -> AsyncIterable[dict[str, Any]]:
    """A PO user in the database"""

    from pytest_simcore.helpers.postgres_users import (
        insert_and_get_user_and_secrets_lifespan,
    )
    from simcore_postgres_database.models.users import UserRole

    async with insert_and_get_user_and_secrets_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        asyncpg_engine,
        email="po-user@email.com",
        name="po-user-fixture",
        role=UserRole.PRODUCT_OWNER,
    ) as record:
        yield record
