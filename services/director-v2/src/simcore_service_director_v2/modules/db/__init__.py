from fastapi import FastAPI
from servicelib.fastapi.db_asyncpg_engine import (
    close_db_connection,
    connect_to_db,
)
from servicelib.fastapi.db_asyncpg_engine import get_engine as get_db_engine
from settings_library.postgres import PostgresSettings


def setup(app: FastAPI, settings: PostgresSettings) -> None:
    async def on_startup() -> None:
        await connect_to_db(app, settings)

    async def on_shutdown() -> None:
        await close_db_connection(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


__all__: tuple[str, ...] = (
    "get_db_engine",
    "setup",
)
