import contextlib
import logging

from fastapi import FastAPI
from servicelib.fastapi.db_asyncpg_engine import close_db_connection, connect_to_db
from servicelib.logging_utils import log_catch, log_context

from ..repository.products import setup_default_product

_logger = logging.getLogger(__name__)


def setup_postgres_database(app: FastAPI):

    async def _():
        with log_context(_logger, logging.INFO, f"{__name__} startup ..."):
            # connection
            await connect_to_db(app, app.state.settings.CATALOG_POSTGRES)

            # configuring default product
            await setup_default_product(app)

        yield

        with log_context(
            _logger, logging.INFO, f"{__name__} shutdown ..."
        ), contextlib.suppress(Exception), log_catch(_logger):
            await close_db_connection(app)

    return _
