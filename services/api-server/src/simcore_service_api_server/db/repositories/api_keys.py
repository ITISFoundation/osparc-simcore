import logging
from typing import NamedTuple

import sqlalchemy as sa
from models_library.products import ProductName
from pydantic.types import PositiveInt
from simcore_postgres_database.aiopg_errors import DatabaseError
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from .. import tables as tbl
from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class UserAndProductTuple(NamedTuple):
    user_id: PositiveInt
    product_name: ProductName


class ApiKeysRepository(BaseRepository):
    """Auth access"""

    async def get_user(
        self,
        connection: AsyncConnection | None = None,
        *,
        api_key: str,
        api_secret: str
    ) -> UserAndProductTuple | None:

        stmt = sa.select(
            tbl.api_keys.c.user_id,
            tbl.api_keys.c.product_name,
        ).where(
            (tbl.api_keys.c.api_key == api_key)  # NOTE: keep order, api_key is indexed
            & (
                tbl.api_keys.c.api_secret
                == sa.func.crypt(api_secret, tbl.api_keys.c.api_secret)
            )
        )
        result: UserAndProductTuple | None = None
        try:
            async with pass_or_acquire_connection(self.db_engine, connection) as conn:
                db_result = await conn.execute(stmt)
                row = db_result.one_or_none()
                if row:
                    result = UserAndProductTuple(
                        user_id=row.user_id, product_name=row.product_name
                    )

        except DatabaseError as err:
            _logger.debug("Failed to get user id: %s", err)

        return result
