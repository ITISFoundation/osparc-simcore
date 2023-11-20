import logging

import sqlalchemy as sa
from aiohttp import web
from models_library.users import GroupID
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.users import users

from ..db.plugin import get_database_engine

_logger = logging.getLogger(__name__)


async def is_user_registered_in_product(
    app: web.Application, email: str, product_group_id: GroupID
) -> bool:
    pg_engine = get_database_engine(app=app)

    async with pg_engine.acquire() as conn:
        user_id = await conn.scalar(
            sa.select(users.c.id)
            .select_from(
                sa.join(user_to_groups, users, user_to_groups.c.uid == users.c.id)
            )
            .where(
                (users.c.email == email) & (user_to_groups.c.gid == product_group_id)
            )
        )
        return user_id is not None
