import logging

import sqlalchemy as sa
from pydantic import BaseModel
from pydantic.types import PositiveInt
from simcore_postgres_database.errors import DatabaseError

from .. import tables as tbl
from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class User(BaseModel):
    user_id: PositiveInt
    product_id: PositiveInt


class ApiKeysRepository(BaseRepository):
    async def get_user(self, api_key: str, api_secret: str) -> User | None:
        stmt = sa.select(tbl.api_keys.c.user_id, tbl.api_keys.c.product_name).where(
            (tbl.api_keys.c.api_key == api_key)
            & (tbl.api_keys.c.api_secret == api_secret),
        )
        user: User | None = None
        try:
            async with self.db_engine.acquire() as conn:
                result = await conn.execute(stmt)
                row = await result.fetchone()
                if row:
                    user = User(user_id=row.user_id, product_id=row.product_name)

        except DatabaseError as err:
            _logger.debug("Failed to get user id: %s", err)

        return user
