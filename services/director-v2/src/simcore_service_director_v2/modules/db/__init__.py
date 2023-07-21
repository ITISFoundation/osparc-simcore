from fastapi import FastAPI
from settings_library.postgres import PostgresSettings

from .events import close_db_connection, connect_to_db


def setup(app: FastAPI, settings: PostgresSettings) -> None:
    async def on_startup() -> None:
        await connect_to_db(app, settings)

    async def on_shutdown() -> None:
        await close_db_connection(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
