import logging
from collections.abc import Callable

from fastapi import FastAPI

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..db.events import close_db_connection, connect_to_db

logger = logging.getLogger(__name__)


def create_start_app_handler(app: FastAPI) -> Callable:
    async def _on_startup() -> None:
        logger.info("Application starting ...")
        if app.state.settings.API_SERVER_POSTGRES:
            # database
            await connect_to_db(app)
            assert app.state.engine  # nosec

        print(APP_STARTED_BANNER_MSG, flush=True)

    return _on_startup


def create_stop_app_handler(app: FastAPI) -> Callable:
    async def _on_shutdown() -> None:
        logger.info("Application stopping, ...")

        if app.state.settings.API_SERVER_POSTGRES:
            try:
                await close_db_connection(app)

            except Exception as err:  # pylint: disable=broad-except
                logger.warning(
                    "Failed to close app: %s",
                    err,
                    exc_info=app.state.settings.debug,
                    stack_info=app.state.settings.debug,
                )

        print(APP_FINISHED_BANNER_MSG, flush=True)

    return _on_shutdown
