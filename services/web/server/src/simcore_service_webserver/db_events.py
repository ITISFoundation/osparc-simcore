from __future__ import annotations

import logging
from typing import AsyncIterator

from aiohttp import web
from aiopg.sa import Engine, create_engine
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from simcore_postgres_database.utils_aiopg import (
    close_engine,
    get_pg_engine_stateinfo,
    raise_if_migration_not_ready,
)
from tenacity._asyncio import AsyncRetrying

from ._meta import APP_NAME
from .constants import APP_SETTINGS_KEY
from .db_settings import PostgresSettings

log = logging.getLogger(__name__)


async def do_connnect_postgress_service(app: web.Application) -> AsyncIterator[None]:
    # STARTUP

    app_settings: "ApplicationSettings" = app[APP_SETTINGS_KEY]
    settings: PostgresSettings = app_settings.WEBSERVER_POSTGRES

    log.info("Creating pg engine with %s", settings.json())

    async for attempt in AsyncRetrying(
        **PostgresRetryPolicyUponInitialization(log).kwargs
    ):
        with attempt:

            engine: Engine = await create_engine(
                str(settings.dsn),
                application_name=settings.POSTGRES_CLIENT_NAME
                or f"{APP_NAME}_{id(app)}",
                minsize=settings.POSTGRES_MINSIZE,
                maxsize=settings.POSTGRES_MAXSIZE,
            )

            try:
                await raise_if_migration_not_ready(engine)
            except Exception:
                await close_engine(engine)
                raise

            app[APP_DB_ENGINE_KEY] = engine

    yield

    # CLEANUP

    engine = app[APP_DB_ENGINE_KEY]
    await close_engine(engine)

    log.debug(
        "engine '%s' after shutdown: %s",
        f"{engine.dsn=}",
        get_pg_engine_stateinfo(engine),
    )
