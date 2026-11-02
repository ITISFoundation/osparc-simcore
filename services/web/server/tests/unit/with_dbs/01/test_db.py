# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import sqlalchemy as sa
from aiohttp.test_utils import TestServer
from simcore_service_webserver.application_settings import (
    ApplicationSettings,
    get_application_settings,
)
from simcore_service_webserver.db import _asyncpg
from simcore_service_webserver.db.db_service import (
    get_engine_state,
    is_service_enabled,
    is_service_responsive,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
    "redis",
    "rabbit",
]


async def test_asyncpg_engine_in_app(web_server: TestServer):
    app = web_server.app
    assert app

    settings: ApplicationSettings = get_application_settings(app)
    assert settings.WEBSERVER_DB
    assert settings.WEBSERVER_DB.POSTGRES_CLIENT_NAME

    sqlalchemy_async_engine: AsyncEngine = _asyncpg.get_async_engine(app)
    assert sqlalchemy_async_engine
    assert isinstance(sqlalchemy_async_engine, AsyncEngine)

    assert sqlalchemy_async_engine.url

    query = sa.text('SELECT "version_num" FROM "alembic_version"')

    async with sqlalchemy_async_engine.connect() as conn:
        result = (await conn.execute(query)).scalar_one_or_none()
    assert result is not None


async def test_responsive(web_server: TestServer):
    app = web_server.app
    assert is_service_enabled(app)
    assert await is_service_responsive(app)


async def test_get_engine_state(web_server: TestServer):
    app = web_server.app
    state = get_engine_state(app)
    assert isinstance(state, dict)
    assert state["checkedin"] == 1
    assert state["checkedout"] == 0
