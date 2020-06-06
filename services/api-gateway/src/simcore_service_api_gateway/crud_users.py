"""
    API layer to access dbs and return ??
"""

from typing import Optional

import sqlalchemy as sa

from . import db
from .models import pg_tables as orm


async def get_user_id(
    conn: db.SAConnection, api_key: str, api_secret: str
) -> Optional[int]:
    stmt = sa.select([orm.api_keys.c.user_id,]).where(
        sa.and_(
            orm.api_keys.c.api_key == api_key, orm.api_keys.c.api_secret == api_secret
        )
    )
    user_id: Optional[int] = await conn.scalar(stmt)
    return user_id


async def any_user_with_id(conn: db.SAConnection, user_id: int) -> bool:
    # FIXME: shall identify api_key or api_secret instead
    stmt = sa.select([orm.api_keys.c.user_id,]).where(orm.api_keys.c.user_id == user_id)
    return (await conn.scalar(stmt)) is not None
