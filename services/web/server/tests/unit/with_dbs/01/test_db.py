# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from pathlib import Path

import sqlalchemy as sa
import yaml
from aiohttp.test_utils import TestServer
from simcore_service_webserver.application_settings import (
    ApplicationSettings,
    get_application_settings,
)
from simcore_service_webserver.db import _asyncpg
from simcore_service_webserver.db.plugin import (
    is_service_enabled,
    is_service_responsive,
)
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_asyncpg_engine_in_app(web_server: TestServer):
    app = web_server.app
    assert app

    settings: ApplicationSettings = get_application_settings(app)
    assert settings.WEBSERVER_DB
    assert settings.WEBSERVER_DB.POSTGRES_CLIENT_NAME

    asyncpg_engine: AsyncEngine = _asyncpg.get_async_engine(app)
    assert asyncpg_engine
    assert isinstance(asyncpg_engine, AsyncEngine)

    assert asyncpg_engine.url

    query = sa.text('SELECT "version_num" FROM "alembic_version"')

    async with asyncpg_engine.connect() as conn:
        result = (await conn.execute(query)).scalar_one_or_none()
    assert result is not None


def test_uses_same_postgres_version(docker_compose_file: Path, osparc_simcore_root_dir: Path):
    with Path.open(docker_compose_file) as fh:
        fixture = yaml.safe_load(fh)

    with Path.open(osparc_simcore_root_dir / "services" / "docker-compose.yml") as fh:
        expected = yaml.safe_load(fh)

    assert fixture["services"]["postgres"]["image"] == expected["services"]["postgres"]["image"]


async def test_responsive(web_server: TestServer):
    app = web_server.app
    assert is_service_enabled(app)
    assert await is_service_responsive(app)
