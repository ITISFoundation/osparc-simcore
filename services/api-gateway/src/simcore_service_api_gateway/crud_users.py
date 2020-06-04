"""
    API layer to access dbs and return schema-based data structures
"""

from typing import Optional

import sqlalchemy as sa

from . import db
from . import db_models as orm
from .schemas import UserInDB, User


fake_users_db = {
    "pcrespov": {
        "name": "pcrespov",
        "full_name": "Pedrito",
        "email": "perico@example.com",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        "disabled": False,
    },
    "alice": {
        "name": "alice",
        "full_name": "Alice Chains",
        "email": "alicechains@example.com",
        "hashed_password": "$2b$12$gSvqqUPvlXP2tfVFaWK1Be7DlH.PKZbv5H8KnzzVgXXbVxpva.pFm",
        "disabled": True,
    },
}


def get_user(username: str) -> Optional[UserInDB]:
    if username in fake_users_db:
        user_dict = fake_users_db[username]
        return UserInDB(**user_dict)
    return None


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


async def get_profile_by_userid(conn: db.SAConnection, user_id: int) -> Optional[User]:
    stmt = sa.select(orm.users).where(orm.users.c.id == user_id)

    res: db.ResultProxy = await conn.execute(stmt)
    row: db.RowProxy = await res.fetchone()

    user = User.from_orm(row)
    return user
