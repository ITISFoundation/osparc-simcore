from typing import Optional

import sqlalchemy as sa
from loguru import logger

from .. import tables as tbl
from .base import BaseRepository
from psycopg2 import DatabaseError

# from ...models.domain.users import User, UserInDB

# For psycopg2 errors SEE https://www.psycopg.org/docs/errors.html#sqlstate-exception-classes

class ApiKeysRepository(BaseRepository):
    async def get_user_id(self, api_key: str, api_secret: str) -> Optional[int]:
        stmt = sa.select([tbl.api_keys.c.user_id,]).where(
            sa.and_(
                tbl.api_keys.c.api_key == api_key,
                tbl.api_keys.c.api_secret == api_secret,
            )
        )

        try:
            user_id: Optional[int] = await self.connection.scalar(stmt)

        except DatabaseError as err:
            logger.debug(f"Failed to get user id: {err}")
            user_id = None

        return user_id

    async def any_user_with_id(self, user_id: int) -> bool:
        # FIXME: shall identify api_key or api_secret instead
        stmt = sa.select([tbl.api_keys.c.user_id,]).where(
            tbl.api_keys.c.user_id == user_id
        )
        return (await self.connection.scalar(stmt)) is not None
