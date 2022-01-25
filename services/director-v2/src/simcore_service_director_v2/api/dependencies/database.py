import logging
from typing import AsyncGenerator, Callable, Type

from aiopg.sa import Engine
from fastapi import Depends, FastAPI
from fastapi.requests import Request

from ...modules.db.repositories import BaseRepository

logger = logging.getLogger(__name__)


def _get_db_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_base_repository(
    engine: Engine, repo_type: Type[BaseRepository]
) -> BaseRepository:
    # NOTE: 2 different ideas were tried here with not so good
    # 1st one was acquiring a connection per repository which lead to the following issue https://github.com/ITISFoundation/osparc-simcore/pull/1966
    # 2nd one was acquiring a connection per request which works but blocks the director-v2 responsiveness once
    # the max amount of connections is reached
    # now the current solution is to acquire connection when needed.

    available_engines = engine.maxsize - (engine.size - engine.freesize)
    if available_engines <= 1:
        logger.warning(
            "Low pg connections available in pool: pool size=%d, acquired=%d, free=%d, reserved=[%d, %d]",
            engine.size,
            engine.size - engine.freesize,
            engine.freesize,
            engine.minsize,
            engine.maxsize,
        )
    return repo_type(db_engine=engine)


def get_repository(repo_type: Type[BaseRepository]) -> Callable:
    async def _get_repo(
        engine: Engine = Depends(_get_db_engine),
    ) -> AsyncGenerator[BaseRepository, None]:
        yield get_base_repository(engine=engine, repo_type=repo_type)

    return _get_repo


def fetch_repo_no_request(
    app: FastAPI, repo_type: Type[BaseRepository]
) -> BaseRepository:
    return get_base_repository(engine=app.state.engine, repo_type=repo_type)
