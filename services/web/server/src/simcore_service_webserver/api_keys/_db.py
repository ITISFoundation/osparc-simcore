import logging
from dataclasses import dataclass
from datetime import timedelta

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.api_keys import api_keys

_logger = logging.getLogger(__name__)


@dataclass
class ApiKeyRepo:
    engine: Engine

    @classmethod
    def create_from_app(cls, app: web.Application):
        return cls(engine=app[APP_DB_ENGINE_KEY])

    async def list_names(
        self, *, user_id: UserID, product_name: ProductName
    ) -> list[str]:
        async with self.engine.acquire() as conn:
            stmt = sa.select(api_keys.c.display_name,).where(
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

    async def delete_by_name(
        self, *, display_name: str, user_id: UserID, product_name: ProductName
    ):
        async with self.engine.acquire() as conn:
            stmt = api_keys.delete().where(
                (api_keys.c.user_id == user_id)
                & (api_keys.c.display_name == display_name)
                & (api_keys.c.product_name == product_name)
            )
            await conn.execute(stmt)

    async def delete_by_key(
        self, *, api_key: str, user_id: UserID, product_name: ProductName
    ):
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
                    (api_keys.c.expires_at != None)  # noqa: E711
                    & (api_keys.c.expires_at < sa.func.now())
                )
                .returning(api_keys.c.display_name)
            )
            result: ResultProxy = await conn.execute(stmt)
            rows = await result.fetchall() or []
            return [r.display_name for r in rows]
