import logging

import sqlalchemy as sa
from models_library.users import UserID
from simcore_postgres_database.storage_models import tokens
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class TokenRepository(BaseRepository):
    async def get_api_token_and_secret(
        self, *, connection: AsyncConnection | None = None, user_id: UserID
    ) -> tuple[str | None, str | None]:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(
                sa.select(
                    tokens,
                ).where(tokens.c.user_id == user_id)
            )
            row = result.one_or_none()
        data = row._asdict() if row else {}

        data = data.get("token_data", {})
        api_token = data.get("token_key")
        api_secret = data.get("token_secret")

        return api_token, api_secret
