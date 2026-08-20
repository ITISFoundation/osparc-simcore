import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.db_asyncpg_engine import close_db_connection, connect_to_db
from servicelib.logging_utils import log_context
from servicelib.tracing import TracingConfig

from ...._meta import APP_NAME

_logger = logging.getLogger(__name__)


def configure_db(app_lifespan: LifespanManager[FastAPI], tracing_config: TracingConfig | None) -> None:
    async def _db_lifespan(app: FastAPI) -> AsyncIterator[State]:
        try:
            with log_context(_logger, logging.INFO, msg="RUT startup DB"):
                await connect_to_db(
                    app,
                    settings=app.state.settings.RESOURCE_USAGE_TRACKER_POSTGRES,
                    application_name=APP_NAME,
                    tracing_config=tracing_config,
                )
            yield {}
        finally:
            if getattr(app.state, "engine", None):
                with log_context(_logger, logging.INFO, msg="RUT shutdown DB"):
                    await close_db_connection(app)

    app_lifespan.add(_db_lifespan)
