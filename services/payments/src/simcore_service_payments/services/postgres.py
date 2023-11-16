from fastapi import FastAPI
from servicelib.db_async_engine import close_db_connection, connect_to_db
from sqlalchemy.ext.asyncio import AsyncEngine

from ..core.settings import ApplicationSettings


def get_engine(app: FastAPI) -> AsyncEngine:
    assert app.state.engine  # nosec
    engine: AsyncEngine = app.state.engine
    return engine


def setup_postgres(app: FastAPI):
    app.state.engine = None

    async def _on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        await connect_to_db(app, settings.PAYMENTS_POSTGRES)
        assert app.state.engine  # nosec
        assert isinstance(app.state.engine, AsyncEngine)  # nosec

    async def _on_shutdown() -> None:
        assert app.state.engine  # nosec
        await close_db_connection(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
