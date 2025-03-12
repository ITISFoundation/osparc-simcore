import logging
from typing import NamedTuple

import sqlalchemy as sa
from models_library.products import ProductName
from pydantic.types import PositiveInt
from simcore_postgres_database.aiopg_errors import DatabaseError

from .. import tables as tbl
from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class UserAndProductTuple(NamedTuple):
    user_id: PositiveInt
    product_name: ProductName


class ApiKeysRepository(BaseRepository):
    async def get_user(
        self, api_key: str, api_secret: str
    ) -> UserAndProductTuple | None:
        stmt = sa.select(tbl.api_keys.c.user_id, tbl.api_keys.c.product_name).where(
            (tbl.api_keys.c.api_key == api_key)
            & (
                sa.func.crypt(api_secret, tbl.api_keys.c.api_secret)
                == tbl.api_keys.c.api_secret
            ),
        )
        result: UserAndProductTuple | None = None
        try:
            async with self.db_engine.acquire() as conn:
                db_result = await conn.execute(stmt)
                row = await db_result.fetchone()
                if row:
                    result = UserAndProductTuple(
                        user_id=row.user_id, product_name=row.product_name
                    )

        except DatabaseError as err:
            _logger.debug("Failed to get user id: %s", err)

        return result
