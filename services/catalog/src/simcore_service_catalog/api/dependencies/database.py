import logging
from typing import AsyncGenerator, Callable, Type

from aiopg.sa import Engine, SAConnection
from fastapi import Depends
from fastapi.requests import Request

from ...db.repositories import BaseRepository

logger = logging.getLogger(__name__)


def _get_db_engine(request: Request) -> Engine:
    return request.app.state.engine


async def _acquire_connection(engine: Engine = Depends(_get_db_engine)) -> SAConnection:
    logger.debug(
        "Acquiring pg connection from pool: pool size=%d, acquired=%d, free=%d, reserved=[%d, %d]",
        engine.size,
        engine.size - engine.freesize,
        engine.freesize,
        engine.minsize,
        engine.maxsize,
    )
    if engine.freesize <= 1:
        logger.warning(
            "Last or no pg connection in pool: pool size=%d, acquired=%d, free=%d, reserved=[%d, %d]",
            engine.size,
            engine.size - engine.freesize,
            engine.freesize,
            engine.minsize,
            engine.maxsize,
        )

    async with engine.acquire() as conn:
        yield conn

    logger.debug(
        "Released pg connection: pool size=%d, acquired=%d, free=%d, reserved=[%d, %d]",
        engine.size,
        engine.size - engine.freesize,
        engine.freesize,
        engine.minsize,
        engine.maxsize,
    )


def get_repository(repo_type: Type[BaseRepository]) -> Callable:
    async def _get_repo(
        db_connection: SAConnection = Depends(_acquire_connection),
    ) -> AsyncGenerator[BaseRepository, None]:

        yield repo_type(db_connection)

    return _get_repo
