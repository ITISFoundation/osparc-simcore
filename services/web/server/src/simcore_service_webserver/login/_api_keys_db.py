import logging
from dataclasses import dataclass
from datetime import timedelta

import simcore_postgres_database.webserver_models as orm
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from models_library.users import UserID
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from sqlalchemy.sql import func

_logger = logging.getLogger(__name__)


@dataclass
class ApiKeyRepo:
    engine: Engine

    @classmethod
    def create_from_app(cls, app: web.Application):
        return cls(engine=app[APP_DB_ENGINE_KEY])

    async def list_names(self, *, user_id: UserID) -> list[str]:
        async with self.engine.acquire() as conn:
            stmt = sa.select(
                [
                    orm.api_keys.c.display_name,
                ]
            ).where(orm.api_keys.c.user_id == user_id)

            result: ResultProxy = await conn.execute(stmt)
            rows = await result.fetchall() or []
            return [r.display_name for r in rows]

    async def create(
        self,
        *,
        display_name: str,
        expiration: timedelta | None,
        user_id: UserID,
        api_key: str,
        api_secret: str,
    ) -> list[IdInt]:
        async with self.engine.acquire() as conn:
            stmt = (
                orm.api_keys.insert()
                .values(
                    display_name=display_name,
                    user_id=user_id,
                    api_key=api_key,
                    api_secret=api_secret,
                    expires_at=(func.now() + expiration) if expiration else None,
                )
                .returning(orm.api_keys.c.id)
            )

            result: ResultProxy = await conn.execute(stmt)
            rows = await result.fetchall() or []
            return [r.id for r in rows]

    async def delete(self, *, display_name: str, user_id: UserID):
        async with self.engine.acquire() as conn:
            stmt = orm.api_keys.delete().where(
                sa.and_(
                    orm.api_keys.c.user_id == user_id,
                    orm.api_keys.c.display_name == display_name,
                )
            )
            await conn.execute(stmt)

    async def prune_expired(self) -> list[str]:
        async with self.engine.acquire() as conn:
            stmt = (
                orm.api_keys.delete()
                .where(
                    (orm.api_keys.c.expires_at != None)  # noqa: E711
                    & (orm.api_keys.c.expires_at < func.now())
                )
                .returning(orm.api_keys.c.display_name)
            )
            result: ResultProxy = await conn.execute(stmt)
            rows = await result.fetchall() or []
            return [r.display_name for r in rows]
