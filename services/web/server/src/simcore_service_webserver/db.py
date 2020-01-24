""" database submodule associated to the postgres uservice


FIXME: _init_db is temporary here so database gets properly initialized
"""

import logging

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import Engine, create_engine
from tenacity import retry

from servicelib.aiopg_utils import (DataSourceName, DBAPIError,
                                    PostgresRetryPolicyUponInitialization)
from servicelib.application_keys import APP_CONFIG_KEY, APP_DB_ENGINE_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .db_config import CONFIG_SECTION_NAME
from .db_models import metadata

THIS_MODULE_NAME  = __name__.split(".")[-1]
THIS_SERVICE_NAME = 'postgres'

log = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(log).kwargs)
async def _create_pg_engine(dsn: DataSourceName, minsize:int, maxsize:int) -> Engine:
    log.info("Creating pg engine for %s", dsn)
    engine = await create_engine(minsize=minsize, maxsize=maxsize, **dsn.asdict())
    return engine

def init_pg_tables(dsn: DataSourceName, schema: sa.schema.MetaData):
    log.info("Initializing tables for %s", dsn)
    try:
        sa_engine = sa.create_engine(dsn.to_uri(with_query=True))
        schema.create_all(sa_engine)
    finally:
        sa_engine.dispose()


async def pg_engine(app: web.Application):
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    pg_cfg = cfg['postgres']

    app[f"{__name__}.dsn"]= dsn = \
        DataSourceName(
            application_name=f'{__name__}_{id(app)}',
            database=pg_cfg['database'],
            user=pg_cfg['user'],
            password=pg_cfg['password'],
            host=pg_cfg['host'],
            port=pg_cfg['port']
        )

    app[APP_DB_ENGINE_KEY] = engine = \
        await _create_pg_engine(dsn, minsize=pg_cfg['minsize'], maxsize=pg_cfg['maxsize'])

    if cfg['init_tables']:
        init_pg_tables(dsn, schema=metadata)

    yield #-------------------

    if engine is not app.get(APP_DB_ENGINE_KEY):
        log.critical("app does not hold right db engine. Somebody has changed it??")

    if engine:
        engine.close()
        await engine.wait_closed()
        log.debug("engine '%s' after shutdown: closed=%s, size=%d", engine.dsn, engine.closed, engine.size)


def is_service_enabled(app: web.Application):
    return app.get(APP_DB_ENGINE_KEY) is not None


async def is_service_responsive(app:web.Application):
    """ Returns true if the app can connect to db service

    """
    if not is_service_enabled(app):
        return False

    engine = app[APP_DB_ENGINE_KEY]
    try:
        async with engine.acquire() as conn:
            await conn.execute("SELECT 1 as is_alive")
            log.debug("%s is alive", THIS_SERVICE_NAME)
            return True
    except DBAPIError as err:
        log.debug("%s is NOT responsive: %s", THIS_SERVICE_NAME, err)
        return False


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup(app: web.Application):
    # ensures keys exist
    app[APP_DB_ENGINE_KEY] = None

    # async connection to db
    # app.on_startup.append(_init_db) # TODO: review how is this disposed
    app.cleanup_ctx.append(pg_engine)


# alias ---
setup_db = setup

__all__ = (
    'setup_db',
    'is_service_enabled'
)
