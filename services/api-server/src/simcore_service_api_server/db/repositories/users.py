from typing import Optional

import sqlalchemy as sa

from ..tables import api_keys, users
from ._base import BaseRepository


class UsersRepository(BaseRepository):
    async def get_user_id(self, api_key: str, api_secret: str) -> Optional[int]:
        stmt = sa.select([api_keys.c.user_id,]).where(
            sa.and_(api_keys.c.api_key == api_key, api_keys.c.api_secret == api_secret,)
        )
        user_id: Optional[int] = await self.connection.scalar(stmt)
        return user_id

    async def any_user_with_id(self, user_id: int) -> bool:
        stmt = sa.select([api_keys.c.user_id,]).where(api_keys.c.user_id == user_id)
        return (await self.connection.scalar(stmt)) is not None

    async def get_email_from_user_id(self, user_id: int) -> Optional[str]:
        stmt = sa.select([users.c.email,]).where(users.c.id == user_id)
        email: Optional[str] = await self.connection.scalar(stmt)
        return email
