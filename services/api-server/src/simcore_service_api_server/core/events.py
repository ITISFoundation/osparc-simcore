import logging
from typing import Callable

from fastapi import FastAPI

from ..db.events import close_db_connection, connect_to_db
from ..services.catalog import close_catalog, setup_catalog
from ..services.remote_debug import setup_remote_debugging
from ..services.webserver import close_webserver, setup_webserver
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

        if app.state.settings.webserver.enabled:
            setup_webserver(app)

        if app.state.settings.catalog.enabled:
            setup_catalog(app)

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:

    # NOTE: that the state is recorded at creation!
    _closing_sequence = [
        (app.state.settings.postgres.enabled, close_db_connection),
        (app.state.settings.webserver.enabled, close_webserver),
        (app.state.settings.catalog.enabled, close_catalog),
    ]

    is_dev = app.state.settings.debug

    async def stop_app() -> None:
        logger.info("Application stopping")

        for enabled, close in _closing_sequence:
            if enabled:
                logger.debug("Closing %s ...", close.__name__)
                try:
                    await close(app)
                except Exception as err:  # pylint: disable=broad-except
                    logger.warning(
                        "Failed to close %s: %s",
                        close.__name__,
                        err,
                        exc_info=is_dev,
                        stack_info=is_dev,
                    )

    return stop_app
