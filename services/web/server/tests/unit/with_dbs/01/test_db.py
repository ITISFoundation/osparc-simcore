# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from pathlib import Path

import aiopg.sa
import asyncpg
import pytest
import sqlalchemy as sa
import yaml
from aiohttp import web
from aiohttp.test_utils import TestServer
from pytest_mock import MockFixture, MockType
from simcore_service_webserver.application_settings import (
    ApplicationSettings,
    get_application_settings,
)
from simcore_service_webserver.db import _aiopg, _asyncpg
from simcore_service_webserver.db.plugin import (
    is_service_enabled,
    is_service_responsive,
    setup_db,
)
from simcore_service_webserver.login.storage import AsyncpgStorage, get_plugin_storage
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def mock_asyncpg_in_setup_db(mocker: MockFixture) -> MockType:

    original_setup = setup_db

    mock_setup_db = mocker.patch(
        "simcore_service_webserver.application.setup_db", autospec=True
    )

    def _wrapper_setup_db(app: web.Application):
        original_setup(app)

        # NEW engine !
        app.cleanup_ctx.append(_asyncpg.postgres_cleanup_ctx)

    mock_setup_db.side_effect = _wrapper_setup_db
    return mock_setup_db


async def test_all_pg_engines_in_app(
    mock_asyncpg_in_setup_db: MockType, web_server: TestServer
):
    assert mock_asyncpg_in_setup_db.called

    app = web_server.app
    assert app

    settings: ApplicationSettings = get_application_settings(app)
    assert settings.WEBSERVER_DB
    assert settings.WEBSERVER_DB.POSTGRES_CLIENT_NAME

    # (1) aiopg engine  (deprecated)
    aiopg_engine = _aiopg.get_database_engine(app)
    assert aiopg_engine
    assert isinstance(aiopg_engine, aiopg.sa.Engine)

    # (2) asyncpg engine via sqlalchemy.ext.asyncio  (new)
    asyncpg_engine: AsyncEngine = _asyncpg.get_async_engine(app)
    assert asyncpg_engine
    assert isinstance(asyncpg_engine, AsyncEngine)

    # (3) low-level asyncpg Pool (deprecated)
    # Will be replaced by (2)
    login_storage: AsyncpgStorage = get_plugin_storage(app)
    assert login_storage.pool
    assert isinstance(login_storage.pool, asyncpg.Pool)

    # they ALL point to the SAME database
    assert aiopg_engine.dsn
    assert asyncpg_engine.url

    query = sa.text('SELECT "version_num" FROM "alembic_version"')
    async with login_storage.pool.acquire() as conn:
        result_pool = await conn.fetchval(str(query))

    async with asyncpg_engine.connect() as conn:
        result_asyncpg = (await conn.execute(query)).scalar_one_or_none()

    async with aiopg_engine.acquire() as conn:
        result_aiopg = await (await conn.execute(query)).scalar()

    assert result_pool == result_asyncpg
    assert result_pool == result_aiopg


def test_uses_same_postgres_version(
    docker_compose_file: Path, osparc_simcore_root_dir: Path
):
    with Path.open(docker_compose_file) as fh:
        fixture = yaml.safe_load(fh)

    with Path.open(osparc_simcore_root_dir / "services" / "docker-compose.yml") as fh:
        expected = yaml.safe_load(fh)

    assert (
        fixture["services"]["postgres"]["image"]
        == expected["services"]["postgres"]["image"]
    )


async def test_responsive(web_server: TestServer):
    app = web_server.app
    assert is_service_enabled(app)
    assert await is_service_responsive(app)
