import logging
from collections.abc import AsyncGenerator, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from ...clients.postgres import get_engine
from ...db.repositories import BaseRepository

_logger = logging.getLogger(__name__)


def get_db_asyncpg_engine(request: Request) -> AsyncEngine:
    return get_engine(request.app)


def get_repository(repo_type: type[BaseRepository]) -> Callable:
    async def _get_repo(
        engine: Annotated[AsyncEngine, Depends(get_db_asyncpg_engine)],
    ) -> AsyncGenerator[BaseRepository, None]:
        # NOTE: 2 different ideas were tried here with not so good
        # 1st one was acquiring a connection per repository which lead to the following issue https://github.com/ITISFoundation/osparc-simcore/pull/1966
        # 2nd one was acquiring a connection per request which works but blocks the director-v2 responsiveness once
        # the max amount of connections is reached
        # now the current solution is to acquire connection when needed.

        # Retrieve connection pool stats from the AsyncEngine
        pool = engine.raw_connection().pool
        available_engines = pool.maxsize - (pool.size - pool.freesize)
        if available_engines <= 1:
            _logger.warning(
                "Low pg connections available in pool: pool size=%d, acquired=%d, free=%d, reserved=[%d, %d]",
                pool.size,
                pool.size - pool.freesize,
                pool.freesize,
                pool.minsize,
                pool.maxsize,
            )
        yield repo_type(db_engine=engine)

    return _get_repo
