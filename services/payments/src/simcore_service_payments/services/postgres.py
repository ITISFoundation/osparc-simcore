from fastapi import FastAPI
from servicelib.db_async_engine import close_db_connection, connect_to_db
from sqlalchemy.ext.asyncio import AsyncEngine

from ..core.settings import ApplicationSettings


def setup_postgres(app: FastAPI):
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        await connect_to_db(app, settings.PAYMENTS_POSTGRES)
        assert app.state.engine  # nosec
        assert isinstance(app.state.engine, AsyncEngine)

    async def on_shutdown() -> None:
        assert app.state.engine  # nosec
        await close_db_connection(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
