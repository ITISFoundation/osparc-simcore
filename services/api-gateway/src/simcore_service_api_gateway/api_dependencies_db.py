from fastapi.requests import Request
from fastapi import FastAPI, Depends

from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection


def _get_app(request: Request) -> FastAPI:
    return request.app


async def get_db_connection(app: FastAPI = Depends(_get_app)) -> SAConnection:
    engine: Engine = app.state.engine
    async with engine.acquire() as conn:
        yield conn
