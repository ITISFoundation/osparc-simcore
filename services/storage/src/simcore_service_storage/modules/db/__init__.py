import logging

from fastapi import FastAPI
from servicelib.fastapi.db_asyncpg_engine import close_db_connection, connect_to_db
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity import retry

from ...core.settings import get_application_settings

_logger = logging.getLogger(__name__)


def setup_db(app: FastAPI) -> None:
    @retry(**PostgresRetryPolicyUponInitialization(_logger).kwargs)
    async def _on_startup() -> None:
        app_settings = get_application_settings(app)
        assert app_settings.STORAGE_POSTGRES is not None  # nosec
        await connect_to_db(app, app_settings.STORAGE_POSTGRES)

    async def _on_shutdown() -> None:
        await close_db_connection(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


def get_db_engine(app: FastAPI) -> AsyncEngine:
    assert isinstance(app.state.engine, AsyncEngine)  # nosec
    return app.state.engine
