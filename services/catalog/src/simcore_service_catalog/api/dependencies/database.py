from typing import AsyncGenerator, Callable, Type

from aiopg.sa import Engine
from fastapi import Depends
from fastapi.requests import Request

from ...db.repositories import BaseRepository


def _get_db_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_repository(repo_type: Type[BaseRepository]) -> Callable:
    async def _get_repo(
        engine: Engine = Depends(_get_db_engine),
    ) -> AsyncGenerator[BaseRepository, None]:
        async with engine.acquire() as conn:
            yield repo_type(conn)

    return _get_repo
