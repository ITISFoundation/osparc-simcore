"""
    API layer to access dbs and return ??
"""

from typing import Optional

import sqlalchemy as sa

from . import db
from . import db_models as orm
from .schemas import UserInDB


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


async def get_user_by_id(conn: db.SAConnection, user_id: int) -> Optional[UserInDB]:
    stmt = sa.select([orm.users,]).where(orm.users.c.id == user_id)

    res: db.ResultProxy = await conn.execute(stmt)
    row: Optional[db.RowProxy] = await res.fetchone()
    return UserInDB.from_orm(row) if row else None


get_profile_by_userid = get_user_by_id
