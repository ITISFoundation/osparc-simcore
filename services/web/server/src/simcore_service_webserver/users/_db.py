import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy
from models_library.users import GroupID, UserID
from simcore_postgres_database.models.users import UserStatus, users
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesRepo,
)
from sqlalchemy.sql import func

from ..db.models import user_to_groups
from ..db.plugin import get_database_engine
from .schemas import Permission


async def do_update_expired_users(conn: SAConnection) -> list[UserID]:
    result: ResultProxy = await conn.execute(
        users.update()
        .values(status=UserStatus.EXPIRED)
        .where(
            (users.c.expires_at.is_not(None))
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


async def list_user_permissions(
    app: web.Application, *, user_id: UserID, product_name: str
) -> list[Permission]:
    engine = get_database_engine(app)

    async with engine.acquire() as conn:
        user_group_extra_properties = (
            await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
                conn, user_id=user_id, product_name=product_name
            )
        )
    return [
        Permission(
            name="override_services_specifications",
            allowed=user_group_extra_properties.override_services_specifications,
        )
    ]
