from typing import Optional

import sqlalchemy as sa

from .. import tables as tbl
from .base import BaseRepository

# from ...models.domain.users import User, UserInDB


class UsersRepository(BaseRepository):
    async def get_user_id(self, api_key: str, api_secret: str) -> Optional[int]:
        stmt = sa.select([tbl.api_keys.c.user_id,]).where(
            sa.and_(
                tbl.api_keys.c.api_key == api_key,
                tbl.api_keys.c.api_secret == api_secret,
            )
        )
        user_id: Optional[int] = await self.connection.scalar(stmt)
        return user_id

    async def any_user_with_id(self, user_id: int) -> bool:
        # FIXME: shall identify api_key or api_secret instead
        stmt = sa.select([tbl.api_keys.c.user_id,]).where(
            tbl.api_keys.c.user_id == user_id
        )
        return (await self.connection.scalar(stmt)) is not None
