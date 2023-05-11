import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.users import UserStatus, users
from sqlalchemy.sql import func

from ..db_models import user_to_groups


async def update_expired_users(engine: Engine) -> list[IdInt]:
    async with engine.acquire() as conn:
        result: ResultProxy = await conn.execute(
            users.update()
            .values(status=UserStatus.EXPIRED)
            .where(
                (users.c.expires_at != None)
                & (users.c.status == UserStatus.ACTIVE)
                & (users.c.expires_at < func.now())
            )
            .returning(users.c.id)
        )
        expired = [r.id for r in await result.fetchall()]
        return expired


async def get_users_for_gid(app: web.Application, gid: int) -> set[int]:
    engine = app[APP_DB_ENGINE_KEY]
    result = set()
    async with engine.acquire() as conn:
        query_result = await conn.execute(
            sa.select(user_to_groups.c.uid).where(user_to_groups.c.gid == gid)
        )
        async for entry in query_result:
            result.add(entry[0])
        return result
