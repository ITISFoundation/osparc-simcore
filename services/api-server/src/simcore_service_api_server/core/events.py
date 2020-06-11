from typing import Callable

from fastapi import FastAPI
from loguru import logger

from ..db.events import close_db_connection, connect_to_db
from ..services.remote_debug import setup_remote_debugging
from .settings import BootModeEnum


def create_start_app_handler(app: FastAPI) -> Callable:
    async def start_app() -> None:
        logger.info("Application started")

        # setup connection to remote debugger (if applies)
        setup_remote_debugging(
            force_enabled=app.state.settings.boot_mode == BootModeEnum.debug
        )

        # setup connection to pg db
        if app.state.settings.postgres_enabled:
            await connect_to_db(app)

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:
    @logger.catch
    async def stop_app() -> None:
        logger.info("Application stopping")
        if app.state.settings.postgres_enabled:
            await close_db_connection(app)

    return stop_app
