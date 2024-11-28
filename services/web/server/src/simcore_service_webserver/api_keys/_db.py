import logging
from datetime import timedelta

import sqlalchemy as sa
from aiohttp import web
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from models_library.basic_types import IdInt
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.models.api_keys import api_keys
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine

_logger = logging.getLogger(__name__)


async def list_names(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> list[str]:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        stmt = sa.select(api_keys.c.display_name).where(
            (api_keys.c.user_id == user_id) & (api_keys.c.product_name == product_name)
        )

        result = await conn.stream(stmt)
        rows = [row async for row in result]
        return [r.display_name for r in rows]


async def create(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    display_name: str,
    expiration: timedelta | None,
    api_key: str,
    api_secret: str,
) -> list[IdInt]:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        stmt = (
            api_keys.insert()
            .values(
                display_name=display_name,
                user_id=user_id,
                product_name=product_name,
                api_key=api_key,
                api_secret=api_secret,
                expires_at=(sa.func.now() + expiration) if expiration else None,
            )
            .returning(api_keys.c.id)
        )

        result = await conn.stream(stmt)
        rows = [row async for row in result]
        return [r.id for r in rows]


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    display_name: str,
    user_id: UserID,
    product_name: ProductName,
) -> ApiKeyInDB | None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        stmt = sa.select(api_keys).where(
            (api_keys.c.user_id == user_id)
            & (api_keys.c.display_name == display_name)
            & (api_keys.c.product_name == product_name)
        )

        result = await conn.stream(stmt)
        row = await result.first()
        return ApiKeyInDB.model_validate(row) if row else None


async def get_or_create(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    display_name: str,
    expiration: timedelta | None,
    api_key: str,
    api_secret: str,
) -> ApiKeyInDB:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        # Implemented as "create or get"
        insert_stmt = (
            pg_insert(api_keys)
            .values(
                display_name=display_name,
                user_id=user_id,
                product_name=product_name,
                api_key=api_key,
                api_secret=api_secret,
                expires_at=(sa.func.now() + expiration) if expiration else None,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "display_name"],
                set_={
                    "product_name": product_name
                },  # dummy enable returning since on_conflict_do_nothing returns None
                # NOTE: use this entry for reference counting in https://github.com/ITISFoundation/osparc-simcore/issues/5875
            )
            .returning(api_keys)
        )

        result = await conn.stream(insert_stmt)
        row = await result.first()
        assert row  # nosec
        return ApiKeyInDB.model_validate(row)


async def delete_by_name(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    display_name: str,
    user_id: UserID,
    product_name: ProductName,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        stmt = api_keys.delete().where(
            (api_keys.c.user_id == user_id)
            & (api_keys.c.display_name == display_name)
            & (api_keys.c.product_name == product_name)
        )
        await conn.execute(stmt)


async def delete_by_key(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    api_key: str,
    user_id: UserID,
    product_name: ProductName,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        stmt = api_keys.delete().where(
            (api_keys.c.user_id == user_id)
            & (api_keys.c.api_key == api_key)
            & (api_keys.c.product_name == product_name)
        )
        await conn.execute(stmt)


async def prune_expired(
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
        result = await conn.stream(stmt)
        rows = [row async for row in result]
        return [r.display_name for r in rows]
