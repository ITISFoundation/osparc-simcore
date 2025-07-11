"""Private user tokens from external services (e.g. dat-core)

Implemented as a stand-alone API but currently only exposed to the handlers
"""

import sqlalchemy as sa
from models_library.users import UserID, UserThirdPartyToken
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import and_, literal_column
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.base_repository import BaseRepository
from ..db.models import tokens
from ..users.exceptions import TokenNotFoundError


class UserTokensRepository(BaseRepository):
    async def create_token(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        token: UserThirdPartyToken,
    ) -> UserThirdPartyToken:
        async with transaction_context(self.engine, connection) as conn:
            await conn.execute(
                tokens.insert().values(
                    user_id=user_id,
                    token_service=token.service,
                    token_data=token.model_dump(mode="json"),
                )
            )
            return token

    async def list_tokens(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
    ) -> list[UserThirdPartyToken]:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            result = await conn.execute(
                sa.select(tokens.c.token_data).where(tokens.c.user_id == user_id)
            )
            return [
                UserThirdPartyToken.model_construct(**row["token_data"])
                for row in result.fetchall()
            ]

    async def get_token(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        service_id: str,
    ) -> UserThirdPartyToken:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            result = await conn.execute(
                sa.select(tokens.c.token_data).where(
                    and_(
                        tokens.c.user_id == user_id,
                        tokens.c.token_service == service_id,
                    )
                )
            )
            if row := result.one_or_none():
                return UserThirdPartyToken.model_construct(**row["token_data"])
            raise TokenNotFoundError(service_id=service_id)

    async def update_token(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        service_id: str,
        token_data: dict[str, str],
    ) -> UserThirdPartyToken:
        async with transaction_context(self.engine, connection) as conn:
            result = await conn.execute(
                sa.select(tokens.c.token_data, tokens.c.token_id).where(
                    (tokens.c.user_id == user_id)
                    & (tokens.c.token_service == service_id)
                )
            )
            row = result.one_or_none()
            if not row:
                raise TokenNotFoundError(service_id=service_id)

            data = dict(row["token_data"])
            tid = row["token_id"]
            data.update(token_data)

            result = await conn.execute(
                tokens.update()
                .where(tokens.c.token_id == tid)
                .values(token_data=data)
                .returning(literal_column("*"))
            )
            updated_token = result.one()
            assert updated_token  # nosec
            return UserThirdPartyToken.model_construct(**updated_token["token_data"])

    async def delete_token(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        service_id: str,
    ) -> None:
        async with transaction_context(self.engine, connection) as conn:
            await conn.execute(
                tokens.delete().where(
                    and_(
                        tokens.c.user_id == user_id,
                        tokens.c.token_service == service_id,
                    )
                )
            )
