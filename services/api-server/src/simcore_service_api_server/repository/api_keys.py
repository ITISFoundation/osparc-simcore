import hashlib
import logging
from typing import Any, NamedTuple

import sqlalchemy as sa
from aiocache import cached  # type: ignore[import-untyped]
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.models.api_keys import api_keys as auth_api_keys_table
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import AUTH_SESSION_TTL_SECONDS, BaseRepository

_logger = logging.getLogger(__name__)


class UserAndProductTuple(NamedTuple):
    user_id: UserID
    product_name: ProductName


def _auth_cache_key(*_args: Any, **kwargs: Any) -> str:
    digest = hashlib.sha256(f"{kwargs['api_key']}:{kwargs['api_secret']}".encode()).hexdigest()
    return f"api_auth:{digest}"


class ApiKeysRepository(BaseRepository):
    """Auth access"""

    @cached(
        ttl=AUTH_SESSION_TTL_SECONDS,
        key_builder=_auth_cache_key,
        namespace=__name__,
        skip_cache_func=lambda user: user is None,
        noself=True,
    )
    async def get_user(
        self,
        connection: AsyncConnection | None = None,
        *,
        api_key: str,
        api_secret: str,
    ) -> UserAndProductTuple | None:
        """Validates API key and secret, returning user info if valid otherwise None.

        WARNING: Cached for 120s TTL, keyed on both api_key and api_secret: a
        cached success is only replayed for the same credential pair.
        NOTE: to disable caching set AIOCACHE_DISABLE=1
        """

        stmt = sa.select(
            auth_api_keys_table.c.user_id,
            auth_api_keys_table.c.product_name,
        ).where(
            (auth_api_keys_table.c.api_key == api_key)  # NOTE: keep order, api_key is indexed
            & (auth_api_keys_table.c.api_secret == sa.func.crypt(api_secret, auth_api_keys_table.c.api_secret))
        )
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(stmt)
            row = result.one_or_none()
            return UserAndProductTuple(user_id=row.user_id, product_name=row.product_name) if row else None
