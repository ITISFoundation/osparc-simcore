"""
Helpers on asyncpg

SEE migration aiopg->asyncpg https://github.com/ITISFoundation/osparc-simcore/issues/4529
"""

import logging
from collections.abc import AsyncIterator

from aiohttp import web
from servicelib.aiohttp.db_asyncpg_engine import (
    close_db_connection,
    connect_to_db,
    get_async_engine,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from .._meta import APP_NAME
from .settings import PostgresSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


async def postgres_cleanup_ctx(app: web.Application) -> AsyncIterator[None]:
    settings: PostgresSettings = get_plugin_settings(app)
    await connect_to_db(app, settings, application_name=APP_NAME)

    assert get_async_engine(app)  # nosec
    assert isinstance(get_async_engine(app), AsyncEngine)  # nosec

    yield

    await close_db_connection(app)


__all__: tuple[str, ...] = (
    "get_async_engine",
    "postgres_cleanup_ctx",
)
