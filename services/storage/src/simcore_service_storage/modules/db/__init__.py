import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from servicelib.fastapi.db_asyncpg_engine import close_db_connection, connect_to_db
from servicelib.fastapi.lifespan_utils import LifespanManager
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity import retry

from ..._meta import APP_NAME
from ...core.settings import get_application_settings

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def _db_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for database connection."""
    app.state.engine = None

    @retry(**PostgresRetryPolicyUponInitialization(_logger).kwargs)
    async def _setup() -> None:
        app_settings = get_application_settings(app)
        assert app_settings.STORAGE_POSTGRES is not None  # nosec
        await connect_to_db(app, app_settings.STORAGE_POSTGRES, application_name=APP_NAME)

    try:
        await _setup()
        yield
    finally:
        await close_db_connection(app)


def configure_db(app_lifespan: LifespanManager) -> None:
    """Configure database lifespan."""
    app_lifespan.add(_db_lifespan)


def get_db_engine(app: FastAPI) -> AsyncEngine:
    assert isinstance(app.state.engine, AsyncEngine)  # nosec
    return app.state.engine
