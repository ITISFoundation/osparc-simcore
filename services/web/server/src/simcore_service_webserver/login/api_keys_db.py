import logging

import simcore_postgres_database.webserver_models as orm
from aiohttp import web
from aiopg.sa.result import ResultProxy
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from sqlalchemy.sql import func

log = logging.getLogger(__name__)


async def prune_expired_api_keys(app: web.Application):
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        stmt = (
            orm.api_keys.delete()
            .where(
                (orm.api_keys.c.expires_at != None)
                & (orm.api_keys.c.expires_at < func.now())
            )
            .returning(orm.api_keys.c.display_name)
        )

        result: ResultProxy = await conn.execute(stmt)
        deleted = [r.display_name for r in await result.fetchall()]
        return deleted
