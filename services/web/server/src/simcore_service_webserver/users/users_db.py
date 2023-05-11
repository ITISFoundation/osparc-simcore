import logging

from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from simcore_postgres_database.models.users import UserStatus, users
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)


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
