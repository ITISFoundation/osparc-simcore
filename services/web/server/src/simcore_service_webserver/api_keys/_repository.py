import logging
from datetime import timedelta

import sqlalchemy as sa
from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.models.api_keys import api_keys
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .models import ApiKey

_logger = logging.getLogger(__name__)


def _hash_secret(secret: str) -> sa.sql.ClauseElement:
    return sa.func.crypt(secret, sa.func.gen_salt("bf", 10))


async def create_api_key(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    display_name: str,
    expiration: timedelta | None,
    api_key: str,
    api_secret: str,
) -> ApiKey:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        stmt = (
            pg_insert(api_keys)
            .values(
                display_name=display_name,
                user_id=user_id,
                product_name=product_name,
                api_key=api_key,
                api_secret=_hash_secret(api_secret),
                expires_at=(sa.func.now() + expiration) if expiration else None,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "display_name"],
                set_={
                    "api_key": api_key,
                    "api_secret": _hash_secret(api_secret),
                    "expires_at": (sa.func.now() + expiration) if expiration else None,
                },
            )
            .returning(api_keys)
        )

        result = await conn.stream(stmt)
        row = await result.one()

        return ApiKey(
            id=f"{row.id}",  # NOTE See: https://github.com/ITISFoundation/osparc-simcore/issues/6919
            display_name=display_name,
            expiration=expiration,
            api_key=api_key,
            api_secret=api_secret,
        )


async def delete_api_key(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    api_key_id: str,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        stmt = api_keys.delete().where(
            (
                api_keys.c.id == int(api_key_id)
            )  # NOTE See: https://github.com/ITISFoundation/osparc-simcore/issues/6919
            & (api_keys.c.user_id == user_id)
            & (api_keys.c.product_name == product_name)
        )
        await conn.execute(stmt)


async def delete_api_key_by_key(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    user_id: UserID,
    api_key: str,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        stmt = api_keys.delete().where(
            (api_keys.c.api_key == api_key)
            & (api_keys.c.user_id == user_id)
            & (api_keys.c.product_name == product_name)
        )
        await conn.execute(stmt)


async def delete_expired_api_keys(
    app: web.Application, connection: AsyncConnection | None = None
) -> list[str]:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        stmt = (
            api_keys.delete()
            .where(
                (api_keys.c.expires_at.is_not(None))
                & (api_keys.c.expires_at < sa.func.now())
            )
            .returning(api_keys.c.display_name)
        )
        result = await conn.execute(stmt)
        rows = result.fetchall()
        return [r.display_name for r in rows]


async def get_api_key(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    api_key_id: str,
    user_id: UserID,
    product_name: ProductName,
) -> ApiKey | None:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        stmt = sa.select(api_keys).where(
            (
                api_keys.c.id == int(api_key_id)
            )  # NOTE See: https://github.com/ITISFoundation/osparc-simcore/issues/6919
            & (api_keys.c.user_id == user_id)
            & (api_keys.c.product_name == product_name)
        )

        result = await conn.execute(stmt)
        row = result.one_or_none()

        return (
            ApiKey(
                id=f"{row.id}",  # NOTE See: https://github.com/ITISFoundation/osparc-simcore/issues/6919
                display_name=row.display_name,
                expiration=row.expires_at,
                api_key=row.api_key,
                api_secret=row.api_secret,
            )
            if row
            else None
        )


async def list_api_keys(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> list[ApiKey]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        stmt = sa.select(api_keys.c.id, api_keys.c.display_name).where(
            (api_keys.c.user_id == user_id) & (api_keys.c.product_name == product_name)
        )

        result = await conn.stream(stmt)
        rows = [row async for row in result]

        return [
            ApiKey(
                id=f"{row.id}",  # NOTE See: https://github.com/ITISFoundation/osparc-simcore/issues/6919
                display_name=row.display_name,
            )
            for row in rows
        ]
