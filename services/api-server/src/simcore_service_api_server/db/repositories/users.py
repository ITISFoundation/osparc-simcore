import sqlalchemy as sa

from ..tables import api_keys, users
from ._base import BaseRepository


class UsersRepository(BaseRepository):
    async def get_user_id(self, api_key: str, api_secret: str) -> int | None:
        stmt = sa.select(api_keys.c.user_id,).where(
            sa.and_(
                api_keys.c.api_key == api_key,
                api_keys.c.api_secret == api_secret,
            )
        )
        async with self.db_engine.acquire() as conn:
            user_id: int | None = await conn.scalar(stmt)
        return user_id

    async def any_user_with_id(self, user_id: int) -> bool:
        stmt = sa.select(
            api_keys.c.user_id,
        ).where(api_keys.c.user_id == user_id)
        async with self.db_engine.acquire() as conn:
            return (await conn.scalar(stmt)) is not None

    async def get_email_from_user_id(self, user_id: int) -> str | None:
        stmt = sa.select(
            users.c.email,
        ).where(users.c.id == user_id)
        async with self.db_engine.acquire() as conn:
            email: str | None = await conn.scalar(stmt)
        return email
