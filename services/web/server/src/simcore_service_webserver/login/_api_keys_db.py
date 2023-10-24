import logging
from dataclasses import dataclass

import simcore_postgres_database.webserver_models as orm
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy
from models_library.api_schemas_webserver.auth import ApiKeyCreate
from models_library.basic_types import IdInt
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.request_keys import RQT_USERID_KEY
from sqlalchemy.sql import func

_logger = logging.getLogger(__name__)


@dataclass
class ApiKeyRepo:
    engine: Engine
    user_id: int | None = None  # =undefined

    @classmethod
    def create_from_app(cls, app: web.Application):
        return cls(engine=app[APP_DB_ENGINE_KEY])

    @classmethod
    def create_from_request(cls, request: web.Request):
        return cls(
            engine=request.app[APP_DB_ENGINE_KEY],
            user_id=request.get(RQT_USERID_KEY, None),
        )

    def _raise_if_no_user_defined(self):
        if self.user_id is None:
            raise ValueError("Unknown user_id")

    async def list_names(self):
        self._raise_if_no_user_defined()
        async with self.engine.acquire() as conn:
            stmt = sa.select(
                [
                    orm.api_keys.c.display_name,
                ]
            ).where(orm.api_keys.c.user_id == self.user_id)

            result: ResultProxy = await conn.execute(stmt)
            rows = await result.fetchall() or []
            return [r.display_name for r in rows]

    async def create(
        self,
        request_data: ApiKeyCreate,
        *,
        api_key: str,
        api_secret: str,
    ) -> list[IdInt]:
        self._raise_if_no_user_defined()
        async with self.engine.acquire() as conn:
            stmt = (
                orm.api_keys.insert()
                .values(
                    display_name=request_data.display_name,
                    user_id=self.user_id,
                    api_key=api_key,
                    api_secret=api_secret,
                    expires_at=func.now() + request_data.expiration
                    if request_data.expiration
                    else None,
                )
                .returning(orm.api_keys.c.id)
            )

            result: ResultProxy = await conn.execute(stmt)
            rows = await result.fetchall() or []
            return [r.id for r in rows]

    async def delete(self, name: str):
        self._raise_if_no_user_defined()
        async with self.engine.acquire() as conn:
            stmt = orm.api_keys.delete().where(
                sa.and_(
                    orm.api_keys.c.user_id == self.user_id,
                    orm.api_keys.c.display_name == name,
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
