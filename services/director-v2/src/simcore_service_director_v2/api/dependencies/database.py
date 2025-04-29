import logging
from collections.abc import AsyncGenerator, Callable
from typing import Annotated, TypeVar, cast

from fastapi import Depends
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from ...modules.db.repositories import BaseRepository

logger = logging.getLogger(__name__)


RepoType = TypeVar("RepoType", bound=BaseRepository)


def _get_db_engine(request: Request) -> AsyncEngine:
    return cast(AsyncEngine, request.app.state.engine)


def get_base_repository(engine: AsyncEngine, repo_type: type[RepoType]) -> RepoType:
    # NOTE: 2 different ideas were tried here with not so good
    # 1st one was acquiring a connection per repository which lead to the following issue https://github.com/ITISFoundation/osparc-simcore/pull/1966
    # 2nd one was acquiring a connection per request which works but blocks the director-v2 responsiveness once
    # the max amount of connections is reached
    # now the current solution is to acquire connection when needed.

    # Get pool metrics
    checkedin = engine.pool.checkedin()  # type: ignore # connections available in pool
    checkedout = engine.pool.checkedout()  # type: ignore # connections in use
    total_size = engine.pool.size()  # type: ignore # current total connections

    if checkedin <= 1:
        logger.warning(
            "Database connection pool near limits: total=%d, in_use=%d, available=%d",
            total_size,
            checkedout,
            checkedin,
        )

    return repo_type(db_engine=engine)


def get_repository(
    repo_type: type[RepoType],
) -> Callable[..., AsyncGenerator[RepoType, None]]:
    async def _get_repo(
        engine: Annotated[AsyncEngine, Depends(_get_db_engine)],
    ) -> AsyncGenerator[RepoType, None]:
        yield get_base_repository(engine=engine, repo_type=repo_type)

    return _get_repo
