# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from pathlib import Path

import aiopg.sa
import asyncpg
import sqlalchemy as sa
import yaml
from aiohttp.test_utils import TestServer
from simcore_service_webserver.application_settings import (
    ApplicationSettings,
    get_application_settings,
)
from simcore_service_webserver.db import _aiopg, _asyncpg
from simcore_service_webserver.db.plugin import (
    is_service_enabled,
    is_service_responsive,
)
from simcore_service_webserver.login._login_repository_legacy import (
    AsyncpgStorage,
    get_plugin_storage,
)
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_all_pg_engines_in_app(web_server: TestServer):
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
