from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.db_async_engine import close_db_connection, connect_to_db
from sqlalchemy.ext.asyncio import AsyncEngine

from ...core.settings import ApplicationSettings


async def lifespan_postgres(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings

    await connect_to_db(app, settings.DYNAMIC_SCHEDULER_POSTGRES)
    assert app.state.engine  # nosec
    assert isinstance(app.state.engine, AsyncEngine)  # nosec

    yield {}

    assert app.state.engine  # nosec
    await close_db_connection(app)
