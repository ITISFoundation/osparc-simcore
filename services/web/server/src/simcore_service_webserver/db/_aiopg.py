"""
Helpers on aiopg

SEE migration aiopg->asyncpg https://github.com/ITISFoundation/osparc-simcore/issues/4529
"""

import logging
from collections.abc import AsyncIterator
from typing import Any, cast

from aiohttp import web
from aiopg.sa import Engine, create_engine
from common_library.json_serialization import json_dumps
from servicelib.aiohttp.aiopg_utils import is_pg_responsive
from servicelib.aiohttp.application_keys import APP_AIOPG_ENGINE_KEY
from servicelib.logging_utils import log_context
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from simcore_postgres_database.errors import DBAPIError
from simcore_postgres_database.utils_aiopg import (
    DBMigrationError,
    close_engine,
    get_pg_engine_stateinfo,
    raise_if_migration_not_ready,
)
from tenacity import retry

from .settings import PostgresSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(_logger).kwargs)
async def _ensure_pg_ready(settings: PostgresSettings) -> Engine:
    engine: Engine = await create_engine(
        settings.dsn,
        application_name=settings.POSTGRES_CLIENT_NAME,
        minsize=settings.POSTGRES_MINSIZE,
        maxsize=settings.POSTGRES_MAXSIZE,
    )

    try:
        await raise_if_migration_not_ready(engine)
    except (DBMigrationError, DBAPIError):
        await close_engine(engine)
        raise

    return engine  # tenacity rules guarantee exit with exc


async def postgres_cleanup_ctx(app: web.Application) -> AsyncIterator[None]:

    settings = get_plugin_settings(app)

    with log_context(
        _logger,
        logging.INFO,
        "Connecting app[APP_AIOPG_ENGINE_KEY] to postgres with %s",
        f"{settings=}",
    ):
        aiopg_engine = await _ensure_pg_ready(settings)
        app[APP_AIOPG_ENGINE_KEY] = aiopg_engine

    _logger.info(
        "app[APP_AIOPG_ENGINE_KEY] created %s",
        json_dumps(get_engine_state(app), indent=1),
    )

    yield  # -------------------

    if aiopg_engine is not app.get(APP_AIOPG_ENGINE_KEY):
        _logger.critical(
            "app[APP_AIOPG_ENGINE_KEY] does not hold right db engine. Somebody has changed it??"
        )

    await close_engine(aiopg_engine)

    _logger.debug(
        "app[APP_AIOPG_ENGINE_KEY] after shutdown %s (closed=%s): %s",
        aiopg_engine.dsn,
        aiopg_engine.closed,
        json_dumps(get_engine_state(app), indent=1),
    )


def is_service_enabled(app: web.Application):
    return app.get(APP_AIOPG_ENGINE_KEY) is not None


async def is_service_responsive(app: web.Application):
    """Returns true if the app can connect to db service"""
    if not is_service_enabled(app):
        return False
    return await is_pg_responsive(engine=app[APP_AIOPG_ENGINE_KEY])


def get_engine_state(app: web.Application) -> dict[str, Any]:
    engine: Engine | None = app.get(APP_AIOPG_ENGINE_KEY)
    if engine:
        pg_engine_stateinfo: dict[str, Any] = get_pg_engine_stateinfo(engine)
        return pg_engine_stateinfo
    return {}


def get_database_engine(app: web.Application) -> Engine:
    return cast(Engine, app[APP_AIOPG_ENGINE_KEY])
