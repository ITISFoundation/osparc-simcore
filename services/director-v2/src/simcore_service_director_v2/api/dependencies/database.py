import logging
import math
from collections.abc import AsyncGenerator, Callable
from typing import Annotated, TypeVar, cast

from fastapi import Depends
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from ...modules.db.repositories import BaseRepository

_logger = logging.getLogger(__name__)

_POOL_UTILIZATION_WARNING_RATIO = 0.9


RepoType = TypeVar("RepoType", bound=BaseRepository)


def _get_db_engine(request: Request) -> AsyncEngine:
    return cast(AsyncEngine, request.app.state.engine)


def _pool_capacity_metrics(engine: AsyncEngine) -> tuple[int, int, int, float]:
    in_use = engine.pool.checkedout()  # type: ignore # connections in use
    pool_size = engine.pool.size()  # type: ignore # configured pool size
    max_overflow = max(int(getattr(engine.pool, "_max_overflow", 0)), 0)

    total_capacity = pool_size + max_overflow
    warning_threshold = math.ceil(total_capacity * _POOL_UTILIZATION_WARNING_RATIO)
    utilization = in_use / total_capacity if total_capacity > 0 else 0.0
    return in_use, warning_threshold, total_capacity, utilization




def get_base_repository[RepoType: BaseRepository](engine: AsyncEngine, repo_type: type[RepoType]) -> RepoType:
    # NOTE: 2 different ideas were tried here with not so good
    # 1st one was acquiring a connection per repository which lead to the following issue https://github.com/ITISFoundation/osparc-simcore/pull/1966
    # 2nd one was acquiring a connection per request which works but blocks the director-v2 responsiveness once
    # the max amount of connections is reached
    # now the current solution is to acquire connection when needed.

    in_use, warning_threshold, total_capacity, utilization = _pool_capacity_metrics(engine)
    if total_capacity > 0 and in_use >= warning_threshold:
        _logger.warning(
            "Database connection pool near limits: checked_out=%s threshold=%s total_capacity=%s "
            "utilization=%.1f%% status=%s",
            in_use,
            warning_threshold,
            total_capacity,
            utilization * 100,
            engine.pool.status(),
        )

    return repo_type(db_engine=engine)


def get_repository[RepoType: BaseRepository](
    repo_type: type[RepoType],
) -> Callable[..., AsyncGenerator[RepoType]]:
    async def _get_repo(
        engine: Annotated[AsyncEngine, Depends(_get_db_engine)],
    ) -> AsyncGenerator[RepoType]:
        yield get_base_repository(engine=engine, repo_type=repo_type)

    return _get_repo
