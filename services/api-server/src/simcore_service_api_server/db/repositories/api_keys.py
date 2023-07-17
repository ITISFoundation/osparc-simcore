import logging

import sqlalchemy as sa
from pydantic.types import PositiveInt
from simcore_postgres_database.errors import DatabaseError

from .. import tables as tbl
from ._base import BaseRepository

logger = logging.getLogger(__name__)


# TODO: see if can use services/api-server/src/simcore_service_api_server/models/domain/api_keys.py
# NOTE: For psycopg2 errors SEE https://www.psycopg.org/docs/errors.html#sqlstate-exception-classes


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
            logger.debug("Failed to get user id: %s", err)
            user_id = None

        return user_id

    async def any_user_with_id(self, user_id: int) -> bool:
        # FIXME: shall identify api_key or api_secret instead
        stmt = sa.select(
            [
                tbl.api_keys.c.user_id,
            ]
        ).where(tbl.api_keys.c.user_id == user_id)
        async with self.db_engine.acquire() as conn:
            return (await conn.scalar(stmt)) is not None
