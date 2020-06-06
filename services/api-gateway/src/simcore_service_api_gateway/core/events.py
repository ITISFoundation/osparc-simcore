from typing import Callable

from fastapi import FastAPI

from loguru import logger

from ..db.events import close_db_connection, connect_to_db
from ..utils.remote_debug import setup_remote_debugging


def create_start_app_handler(app: FastAPI) -> Callable:
    async def start_app() -> None:
        logger.info("Application started")
        setup_remote_debugging()
        await connect_to_db(app)

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:
    # @logger.catch
    async def stop_app() -> None:
        logger.info("Application stopping")
        await close_db_connection(app)

    return stop_app
