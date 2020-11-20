from fastapi import FastAPI
from ...core.settings import PostgresSettings
from .events import connect_to_db, close_db_connection


def setup(app: FastAPI, settings: PostgresSettings):
    if not settings:
        settings = PostgresSettings()

    async def on_startup() -> None:
        await connect_to_db(app, settings)

    async def on_shutdown() -> None:
        await close_db_connection(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
