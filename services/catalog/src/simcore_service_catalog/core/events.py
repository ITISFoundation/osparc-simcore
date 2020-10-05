import asyncio
import logging
from typing import Callable

from fastapi import FastAPI

from ..db.events import close_db_connection, connect_to_db
from ..services.director import close_director, setup_director
from ..services.remote_debug import setup_remote_debugging
from .background_tasks import start_registry_sync_task, stop_registry_sync_task
from .settings import BootModeEnum

logger = logging.getLogger(__name__)


def create_start_app_handler(app: FastAPI) -> Callable:
    async def start_app() -> None:
        logger.info("Application started")

        # setup connection to remote debugger (if applies)
        setup_remote_debugging(
            force_enabled=app.state.settings.boot_mode == BootModeEnum.DEBUG
        )

        # setup connection to pg db
        if app.state.settings.postgres.enabled:
            # FIXME: check postgres service is in place and ready. Hand-shake?
            await connect_to_db(app)

        # setup connection to director
        setup_director(app)

        if app.state.settings.director.enabled:
            # FIXME: check director service is in place and ready. Hand-shake??
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1728
            await start_registry_sync_task(app)

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:
    async def stop_app() -> None:
        logger.info("Application stopping")
        close_tasks = []
        if app.state.settings.postgres.enabled:
            close_tasks.append(close_db_connection(app))
        if app.state.settings.director.enabled:
            close_tasks.append(stop_registry_sync_task(app))
            close_tasks.append(close_director(app))

        if close_tasks:
            results = await asyncio.gather(*close_tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    logger.error("Failure while closing: %s", res)

    return stop_app
