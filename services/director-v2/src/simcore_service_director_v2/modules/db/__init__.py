from typing import cast

from aiopg.sa import Engine
from fastapi import FastAPI
from settings_library.postgres import PostgresSettings

from ._asyncpg import (
    asyncpg_close_db_connection,
    asyncpg_connect_to_db,
    get_asyncpg_engine,
)
from .events import close_db_connection, connect_to_db


def setup(app: FastAPI, settings: PostgresSettings) -> None:
    async def on_startup() -> None:
        await connect_to_db(app, settings)
        await asyncpg_connect_to_db(app, settings)

    async def on_shutdown() -> None:
        await asyncpg_close_db_connection(app)
        await close_db_connection(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_db_engine(app: FastAPI) -> Engine:
    return cast(Engine, app.state.engine)


__all__: tuple[str, ...] = (
    "get_asyncpg_engine",
    "get_db_engine",
)
