import logging
from typing import Callable

from fastapi import FastAPI
from models_library.basic_types import BootModeEnum
from servicelib.db_async_engine import close_db_connection, connect_to_db

from ..db.events import setup_default_product
from ..services.director import close_director, setup_director
from ..services.remote_debug import setup_remote_debugging
from .background_tasks import start_registry_sync_task, stop_registry_sync_task

logger = logging.getLogger(__name__)


def create_start_app_handler(app: FastAPI) -> Callable:
    async def start_app() -> None:
        logger.info("Application started")

        # setup connection to remote debugger (if applies)
        setup_remote_debugging(
            force_enabled=app.state.settings.SC_BOOT_MODE == BootModeEnum.DEBUG
        )

        # setup connection to pg db
        if app.state.settings.CATALOG_POSTGRES:
            await connect_to_db(app, app.state.settings.CATALOG_POSTGRES)
            await setup_default_product(app)

        if app.state.settings.CATALOG_DIRECTOR:
            # setup connection to director
            await setup_director(app)

            # FIXME: check director service is in place and ready. Hand-shake??
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1728
            await start_registry_sync_task(app)

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:
    async def stop_app() -> None:
        logger.info("Application stopping")
        if app.state.settings.CATALOG_DIRECTOR:
            try:
                await stop_registry_sync_task(app)
                await close_director(app)
                await close_db_connection(app)
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "Unexpected error while closing application", exc_info=True
                )

    return stop_app
