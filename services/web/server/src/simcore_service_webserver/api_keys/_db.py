import logging
from dataclasses import dataclass
from datetime import timedelta

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from models_library.basic_types import IdInt
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.models.api_keys import api_keys
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db.plugin import get_database_engine

_logger = logging.getLogger(__name__)


@dataclass
class ApiKeyRepo:
    engine: Engine

    @classmethod
    def create_from_app(cls, app: web.Application):
        return cls(engine=get_database_engine(app))

    async def list_names(
        self, *, user_id: UserID, product_name: ProductName
    ) -> list[str]:
        async with self.engine.acquire() as conn:
            stmt = sa.select(api_keys.c.display_name).where(
                (api_keys.c.user_id == user_id)
                & (api_keys.c.product_name == product_name)
            )

            result: ResultProxy = await conn.execute(stmt)
            rows = await result.fetchall() or []
            return [r.display_name for r in rows]

    async def create(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        display_name: str,
        expiration: timedelta | None,
        api_key: str,
        api_secret: str,
    ) -> list[IdInt]:
        async with self.engine.acquire() as conn:
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

            result: ResultProxy = await conn.execute(stmt)
            rows = await result.fetchall() or []
            return [r.id for r in rows]

    async def get(
        self, *, display_name: str, user_id: UserID, product_name: ProductName
    ) -> ApiKeyInDB | None:
        async with self.engine.acquire() as conn:
            stmt = sa.select(api_keys).where(
                (api_keys.c.user_id == user_id)
                & (api_keys.c.display_name == display_name)
                & (api_keys.c.product_name == product_name)
            )

            result: ResultProxy = await conn.execute(stmt)
            row: RowProxy | None = await result.fetchone()
            return ApiKeyInDB.model_validate(row) if row else None

    async def get_or_create(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        display_name: str,
        expiration: timedelta | None,
        api_key: str,
        api_secret: str,
    ) -> ApiKeyInDB:
        async with self.engine.acquire() as conn:
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

            result = await conn.execute(insert_stmt)
            row = await result.fetchone()
            assert row  # nosec
            return ApiKeyInDB.model_validate(row)

    async def delete_by_name(
        self, *, display_name: str, user_id: UserID, product_name: ProductName
    ) -> None:
        async with self.engine.acquire() as conn:
            stmt = api_keys.delete().where(
                (api_keys.c.user_id == user_id)
                & (api_keys.c.display_name == display_name)
                & (api_keys.c.product_name == product_name)
            )
            await conn.execute(stmt)

    async def delete_by_key(
        self, *, api_key: str, user_id: UserID, product_name: ProductName
    ) -> None:
        async with self.engine.acquire() as conn:
            stmt = api_keys.delete().where(
                (api_keys.c.user_id == user_id)
                & (api_keys.c.api_key == api_key)
                & (api_keys.c.product_name == product_name)
            )
            await conn.execute(stmt)

    async def prune_expired(self) -> list[str]:
        async with self.engine.acquire() as conn:
            stmt = (
                api_keys.delete()
                .where(
                    (api_keys.c.expires_at.is_not(None))
                    & (api_keys.c.expires_at < sa.func.now())
                )
                .returning(api_keys.c.display_name)
            )
            result: ResultProxy = await conn.execute(stmt)
            rows = await result.fetchall() or []
            return [r.display_name for r in rows]
