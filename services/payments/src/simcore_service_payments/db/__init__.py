from fastapi import FastAPI
from servicelib.db_async_engine import close_db_connection, connect_to_db

from ..core.settings import ApplicationSettings


def setup_db(app: FastAPI):
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        await connect_to_db(app, settings.PAYMENTS_POSTGRES)

    async def on_shutdown() -> None:
        await close_db_connection(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
