import logging
from collections.abc import AsyncGenerator, Callable
from typing import TypeVar, cast

from aiopg.sa import Engine
from fastapi import Depends, FastAPI
from fastapi.requests import Request

from ...modules.db.repositories import BaseRepository

logger = logging.getLogger(__name__)


RepoType = TypeVar("RepoType", bound=BaseRepository)


def _get_db_engine(request: Request) -> Engine:
    return cast(Engine, request.app.state.engine)


def get_base_repository(engine: Engine, repo_type: type[RepoType]) -> RepoType:
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


def get_repository(
    repo_type: type[RepoType],
) -> Callable[..., AsyncGenerator[RepoType, None]]:
    async def _get_repo(
        engine: Engine = Depends(_get_db_engine),
    ) -> AsyncGenerator[RepoType, None]:
        yield get_base_repository(engine=engine, repo_type=repo_type)

    return _get_repo


def get_repository_instance(app: FastAPI, repo_type: type[RepoType]) -> RepoType:
    """
    Retrieves an instance of the specified repository type using the database engine from the FastAPI app.
    """
    engine = cast(Engine, app.state.engine)
    return get_base_repository(engine=engine, repo_type=repo_type)
