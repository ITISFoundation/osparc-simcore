import logging

import sqlalchemy as sa
from pydantic.types import PositiveInt
from simcore_postgres_database.errors import DatabaseError

from .. import tables as tbl
from ._base import BaseRepository

_logger = logging.getLogger(__name__)

UserAndProduct = tuple[PositiveInt, PositiveInt]


class ApiKeysRepository(BaseRepository):
    async def get_user(self, api_key: str, api_secret: str) -> UserAndProduct | None:
        stmt = sa.select(tbl.api_keys.c.user_id, tbl.api_keys.c.product_name).where(
            (tbl.api_keys.c.api_key == api_key)
            & (tbl.api_keys.c.api_secret == api_secret),
        )
        result: UserAndProduct | None = None
        try:
            async with self.db_engine.acquire() as conn:
                db_result = await conn.execute(stmt)
                row = await db_result.fetchone()
                if row:
                    result = (row.user_id, row.product_name)

        except DatabaseError as err:
            _logger.debug("Failed to get user id: %s", err)

        return result
