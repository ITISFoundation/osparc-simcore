import logging

from fastapi import FastAPI
from servicelib.fastapi.db_asyncpg_engine import close_db_connection, connect_to_db
from servicelib.logging_utils import log_context

_logger = logging.getLogger(__name__)


def setup(app: FastAPI):
    async def on_startup() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="RUT startup DB",
        ):
            await connect_to_db(app, app.state.settings.RESOURCE_USAGE_TRACKER_POSTGRES)

    async def on_shutdown() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="RUT shutdown DB",
        ):
            await close_db_connection(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
