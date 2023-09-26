import logging

import sqlalchemy as sa
from pydantic.types import PositiveInt
from simcore_postgres_database.errors import DatabaseError

from .. import tables as tbl
from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class ApiKeysRepository(BaseRepository):
    async def get_user_id(self, api_key: str, api_secret: str) -> PositiveInt | None:
        stmt = sa.select(tbl.api_keys.c.user_id,).where(
            sa.and_(
                tbl.api_keys.c.api_key == api_key,
                tbl.api_keys.c.api_secret == api_secret,
            )
        )

        try:
            async with self.db_engine.acquire() as conn:
                user_id: PositiveInt | None = await conn.scalar(stmt)

        except DatabaseError as err:
            _logger.debug("Failed to get user id: %s", err)
            user_id = None

        return user_id
