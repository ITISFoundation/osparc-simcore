from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.users import UserID

from ..constants import RQT_USERID_KEY
from . import _aiopg


class BaseRepository:
    def __init__(self, engine: Engine, user_id: UserID | None = None):
        self._engine = engine
        self._user_id = user_id

        assert isinstance(self._engine, Engine)  # nosec

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
    def engine(self) -> Engine:
        return self._engine

    @property
    def user_id(self) -> int | None:
        return self._user_id
