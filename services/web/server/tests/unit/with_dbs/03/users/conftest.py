# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
from collections.abc import AsyncIterable, Callable
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestServer
from faker import Faker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import get_asyncpg_engine, setup_db
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def web_server(
    event_loop: asyncio.AbstractEventLoop,
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

    return event_loop.run_until_complete(
        aiohttp_server(app, port=webserver_test_server_port)
    )


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
async def product_owner_user(
    faker: Faker,
    asyncpg_engine: AsyncEngine,
) -> AsyncIterable[dict[str, Any]]:
    """A PO user in the database"""

    from pytest_simcore.helpers.faker_factories import (
        random_user,
    )
    from pytest_simcore.helpers.postgres_tools import (
        insert_and_get_row_lifespan,
    )
    from simcore_postgres_database.models.users import UserRole, users

    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        asyncpg_engine,
        table=users,
        values=random_user(
            faker,
            email="po-user@email.com",
            name="po-user-fixture",
            role=UserRole.PRODUCT_OWNER,
        ),
        pk_col=users.c.id,
    ) as record:
        yield record
