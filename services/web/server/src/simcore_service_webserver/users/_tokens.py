""" Private user tokens from external services (e.g. dat-core)

    Implemented as a stand-alone API but currently only exposed to the handlers
"""
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import RowProxy
from models_library.users import UserID
from sqlalchemy import and_, literal_column

from ..db.db_models import tokens
from ..db.plugin import get_database_engine
from .exceptions import TokenNotFoundError


async def create_token(
    app: web.Application, user_id: UserID, token_data: dict[str, str]
) -> dict[str, str]:
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(
            tokens.insert().values(
                user_id=user_id,
                token_service=token_data["service"],
                token_data=token_data,
            )
        )
        return token_data


async def list_tokens(app: web.Application, user_id: UserID) -> list[dict[str, str]]:
    user_tokens = []
    async with get_database_engine(app).acquire() as conn:
        async for row in conn.execute(
            sa.select(tokens.c.token_data).where(tokens.c.user_id == user_id)
        ):
            user_tokens.append(row["token_data"])
        return user_tokens


async def get_token(
    app: web.Application, user_id: UserID, service_id: str
) -> dict[str, str]:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            sa.select(tokens.c.token_data).where(
                and_(tokens.c.user_id == user_id, tokens.c.token_service == service_id)
            )
        )
        if row := await result.first():
            return dict(row["token_data"])
        raise TokenNotFoundError(service_id=service_id)


async def update_token(
    app: web.Application, user_id: UserID, service_id: str, token_data: dict[str, str]
) -> dict[str, str]:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            sa.select(tokens.c.token_data, tokens.c.token_id).where(
                (tokens.c.user_id == user_id) & (tokens.c.token_service == service_id)
            )
        )
        row = await result.first()
        if not row:
            raise TokenNotFoundError(service_id=service_id)

        data = dict(row["token_data"])
        tid = row["token_id"]
        data.update(token_data)

        resp = await conn.execute(
            # pylint: disable=no-value-for-parameter
            tokens.update()
            .where(tokens.c.token_id == tid)
            .values(token_data=data)
            .returning(literal_column("*"))
        )
        assert resp.rowcount == 1  # nosec
        updated_token: RowProxy = await resp.fetchone()
        return dict(updated_token["token_data"])


async def delete_token(app: web.Application, user_id: UserID, service_id: str) -> None:
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            tokens.delete().where(
                and_(tokens.c.user_id == user_id, tokens.c.token_service == service_id)
            )
        )
