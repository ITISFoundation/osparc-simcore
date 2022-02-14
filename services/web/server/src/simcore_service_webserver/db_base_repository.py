#  a repo: retrieves engine from app
# TODO: a repo: some members acquire and retrieve connection
# TODO: a repo: any validation error in a repo is due to corrupt data in db!

from typing import Optional

from aiohttp import web
from aiopg.sa.engine import Engine

from ._constants import APP_DB_ENGINE_KEY, RQT_USERID_KEY


class BaseRepository:
    """
    Shall be created on every request

    """

    def __init__(self, request: web.Request):
        #  user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]

        self._engine: Engine = request.app[APP_DB_ENGINE_KEY]
        self._user_id: Optional[int] = request.get(RQT_USERID_KEY)

        assert isinstance(self._engine, Engine)  # nosec

    @property
    def engine(self) -> Engine:
        return self._engine

    @property
    def user_id(self) -> Optional[int]:
        return self._user_id
