from aiohttp import web
from aiopg.sa.engine import Engine

from .._constants import APP_DB_ENGINE_KEY, RQT_USERID_KEY


class BaseRepository:
    def __init__(self, request: web.Request):
        self._engine: Engine = request.app[APP_DB_ENGINE_KEY]
        self._user_id: int | None = request.get(RQT_USERID_KEY)

        assert isinstance(self._engine, Engine)  # nosec

    @property
    def engine(self) -> Engine:
        return self._engine

    @property
    def user_id(self) -> int | None:
        return self._user_id
