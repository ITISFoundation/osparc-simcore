import logging
from typing import Callable

from fastapi import FastAPI

from ..db.events import close_db_connection, connect_to_db
from ..services.remote_debug import setup_remote_debugging
from .settings import BootModeEnum

logger = logging.getLogger(__name__)


def create_start_app_handler(app: FastAPI) -> Callable:
    async def start_app() -> None:
        logger.info("Application started")

        # setup connection to remote debugger (if applies)
        setup_remote_debugging(
            force_enabled=app.state.settings.boot_mode == BootModeEnum.debug
        )

        # setup connection to pg db
        if app.state.settings.postgres.enabled:
            await connect_to_db(app)

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:
    async def stop_app() -> None:
        try:
            logger.info("Application stopping")
            if app.state.settings.postgres.enabled:
                await close_db_connection(app)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Stopping application")

    return stop_app
