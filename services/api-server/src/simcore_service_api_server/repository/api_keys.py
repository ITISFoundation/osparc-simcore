import logging
from typing import NamedTuple

import sqlalchemy as sa
from models_library.products import ProductName
from pydantic.types import PositiveInt
from simcore_postgres_database.models.api_keys import api_keys as auth_api_keys_table
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

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
            auth_api_keys_table.c.user_id,
            auth_api_keys_table.c.product_name,
        ).where(
            (
                auth_api_keys_table.c.api_key == api_key
            )  # NOTE: keep order, api_key is indexed
            & (
                auth_api_keys_table.c.api_secret
                == sa.func.crypt(api_secret, auth_api_keys_table.c.api_secret)
            )
        )
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(stmt)
            row = result.one_or_none()
            return (
                UserAndProductTuple(user_id=row.user_id, product_name=row.product_name)
                if row
                else None
            )
