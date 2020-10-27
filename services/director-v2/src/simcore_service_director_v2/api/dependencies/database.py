import logging
from typing import AsyncGenerator, Callable, Type

from aiopg.sa import Engine
from fastapi import Depends
from fastapi.requests import Request

from ...modules.db.repositories import BaseRepository

logger = logging.getLogger(__name__)


def _get_db_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_repository(repo_type: Type[BaseRepository]) -> Callable:
    async def _get_repo(
        engine: Engine = Depends(_get_db_engine),
    ) -> AsyncGenerator[BaseRepository, None]:

        logger.debug(
            "Acquiring pg connection from pool: current=%d, free=%d, reserved=[%d, %d]",
            engine.size,
            engine.freesize,
            engine.minsize,
            engine.maxsize,
        )
        if engine.freesize <= 1:
            logger.warning(
                "Last or no pg connection in pool: current=%d, free=%d, reserved=[%d, %d]",
                engine.size,
                engine.freesize,
                engine.minsize,
                engine.maxsize,
            )

        async with engine.acquire() as conn:
            yield repo_type(conn)

        logger.debug(
            "Released pg connection: current=%d, free=%d, reserved=[%d, %d]",
            engine.size,
            engine.freesize,
            engine.minsize,
            engine.maxsize,
        )

    return _get_repo
