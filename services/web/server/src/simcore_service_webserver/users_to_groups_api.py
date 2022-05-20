from typing import Set

import sqlalchemy as sa
from aiohttp import web
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY

from .db_models import user_to_groups


async def get_users_for_gid(app: web.Application, gid: int) -> Set[int]:
    engine = app[APP_DB_ENGINE_KEY]
    result = set()
    async with engine.acquire() as conn:
        query_result = await conn.execute(
            sa.select([user_to_groups.c.uid]).where(user_to_groups.c.gid == gid)
        )
        async for entry in query_result:
            result.add(entry[0])
        return result
