import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy
from models_library.users import GroupID, UserID
from simcore_postgres_database.models.users import UserStatus, users
from sqlalchemy.sql import func

from ..db.db_models import user_to_groups


async def do_update_expired_users(conn: SAConnection) -> list[UserID]:

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
    if rows := await result.fetchall():
        expired = [r.id for r in rows]
        return expired
    return []


async def get_users_ids_in_group(conn: SAConnection, gid: GroupID) -> set[UserID]:
    result: set[UserID] = set()
    query_result = await conn.execute(
        sa.select(user_to_groups.c.uid).where(user_to_groups.c.gid == gid)
    )
    async for entry in query_result:
        result.add(entry[0])
    return result
