from typing import Self

import aiopg.sa
from aiohttp import web
from attr import dataclass
from models_library.users import UserID
from sqlalchemy.ext.asyncio import AsyncEngine

from ..constants import RQT_USERID_KEY
from . import _aiopg, _asyncpg


class BaseRepository:
    def __init__(self, engine: aiopg.sa.Engine, user_id: UserID | None = None):
        self._engine = engine
        self._user_id = user_id

        assert isinstance(self._engine, aiopg.sa.Engine)  # nosec

    @classmethod
    def create_from_request(cls, request: web.Request):
        return cls(
            engine=_aiopg.get_database_engine(request.app),
            user_id=request.get(RQT_USERID_KEY),
        )

    @classmethod
    def create_from_app(cls, app: web.Application):
        return cls(engine=_aiopg.get_database_engine(app), user_id=None)

    @property
    def engine(self) -> aiopg.sa.Engine:
        return self._engine

    @property
    def user_id(self) -> int | None:
        return self._user_id


@dataclass(frozen=True)
class BaseRepositoryV2:
    # NOTE: Will replace BaseRepository
    # https://github.com/ITISFoundation/osparc-simcore/issues/4529
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
