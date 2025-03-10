from dataclasses import dataclass
from typing import Self

from aiohttp import web
from models_library.users import UserID
from sqlalchemy.ext.asyncio import AsyncEngine

from ..constants import RQT_USERID_KEY
from . import _asyncpg


@dataclass(frozen=True)
class BaseRepository:
    engine: AsyncEngine
    user_id: UserID | None = None

    @classmethod
    def create_from_request(cls, request: web.Request) -> Self:
        return cls(
            engine=_asyncpg.get_async_engine(request.app),
            user_id=request.get(RQT_USERID_KEY),
        )

    @classmethod
    def create_from_app(cls, app: web.Application) -> Self:
        return cls(engine=_asyncpg.get_async_engine(app))
