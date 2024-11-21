"""
Helpers on asyncpg specific for aiohttp

SEE migration aiopg->asyncpg https://github.com/ITISFoundation/osparc-simcore/issues/4529
"""


import logging
from typing import Final

from aiohttp import web
from servicelib.logging_utils import log_context
from settings_library.postgres import PostgresSettings
from simcore_postgres_database.utils_aiosqlalchemy import (  # type: ignore[import-not-found] # this on is unclear
    get_pg_engine_stateinfo,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from ..db_asyncpg_utils import create_async_engine_and_pg_database_ready
from ..logging_utils import log_context

APP_DB_ASYNC_ENGINE_KEY: Final[str] = f"{__name__ }.AsyncEngine"


_logger = logging.getLogger(__name__)


def _set_async_engine_to_app_state(app: web.Application, engine: AsyncEngine):
    if exists := app.get(APP_DB_ASYNC_ENGINE_KEY, None):
        msg = f"An instance of {type(exists)} already in app[{APP_DB_ASYNC_ENGINE_KEY}]={exists}"
        raise ValueError(msg)

    app[APP_DB_ASYNC_ENGINE_KEY] = engine
    return get_async_engine(app)


def get_async_engine(app: web.Application) -> AsyncEngine:
    engine: AsyncEngine = app[APP_DB_ASYNC_ENGINE_KEY]
    assert engine  # nosec
    return engine


async def connect_to_db(app: web.Application, settings: PostgresSettings) -> None:
    """
    - db services up, data migrated and ready to use
    - sets an engine in app state (use `get_async_engine(app)` to retrieve)
    """
    if settings.POSTGRES_CLIENT_NAME:
        settings = settings.model_copy(
            update={"POSTGRES_CLIENT_NAME": settings.POSTGRES_CLIENT_NAME + "-asyncpg"}
        )

    with log_context(
        _logger,
        logging.INFO,
        "Connecting app[APP_DB_ASYNC_ENGINE_KEY] to postgres with %s",
        f"{settings=}",
    ):
        engine = await create_async_engine_and_pg_database_ready(settings)
        _set_async_engine_to_app_state(app, engine)

    _logger.info(
        "app[APP_DB_ASYNC_ENGINE_KEY] ready : %s",
        await get_pg_engine_stateinfo(engine),
    )


async def close_db_connection(app: web.Application) -> None:
    engine = get_async_engine(app)
    with log_context(
        _logger, logging.DEBUG, f"app[APP_DB_ASYNC_ENGINE_KEY] disconnect of {engine}"
    ):
        if engine:
            await engine.dispose()
