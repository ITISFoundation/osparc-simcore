from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.users import UserID

from .._constants import APP_DB_ENGINE_KEY, RQT_USERID_KEY


class BaseRepository:
    def __init__(self, engine: Engine, user_id: UserID | None = None):
        self._engine = engine
        self._user_id = user_id

        assert isinstance(self._engine, Engine)  # nosec

    @classmethod
    def create_from_request(cls, request: web.Request):
        return cls(
            engine=request.app[APP_DB_ENGINE_KEY], user_id=request.get(RQT_USERID_KEY)
        )

    @classmethod
    def create_from_app(cls, app: web.Application):
        return cls(engine=app[APP_DB_ENGINE_KEY], user_id=None)

    @property
    def engine(self) -> Engine:
        return self._engine

    @property
    def user_id(self) -> int | None:
        return self._user_id
