import logging
from typing import Callable

from fastapi import FastAPI
from models_library.basic_types import BootModeEnum
from servicelib.fastapi.tracing import setup_tracing

from ..db.events import close_db_connection, connect_to_db, setup_default_product
from ..meta import PROJECT_NAME, __version__
from ..services.director import close_director, setup_director
from ..services.remote_debug import setup_remote_debugging
from .background_tasks import start_registry_sync_task, stop_registry_sync_task

logger = logging.getLogger(__name__)

#
# SEE https://patorjk.com/software/taag/#p=display&h=0&f=Ogre&t=Catalog
#
WELCOME_MSG = r"""
   ___         _           _
  / __\  __ _ | |_   __ _ | |  ___    __ _
 / /    / _` || __| / _` || | / _ \  / _` |
/ /___ | (_| || |_ | (_| || || (_) || (_| |
\____/  \__,_| \__| \__,_||_| \___/  \__, |
                                     |___/     {}
""".format(
    f"v{__version__}"
)


def on_startup() -> None:
    print(WELCOME_MSG, flush=True)


def on_shutdown() -> None:
    msg = PROJECT_NAME + f" v{__version__} SHUT DOWN"
    print(f"{msg:=^100}", flush=True)


def create_start_app_handler(app: FastAPI) -> Callable:
    async def start_app() -> None:
        logger.info("Application started")

        # setup connection to remote debugger (if applies)
        setup_remote_debugging(
            force_enabled=app.state.settings.SC_BOOT_MODE == BootModeEnum.DEBUG
        )

        # setup connection to pg db
        if app.state.settings.CATALOG_POSTGRES:
            await connect_to_db(app)
            await setup_default_product(app)

        if app.state.settings.CATALOG_DIRECTOR:
            # setup connection to director
            await setup_director(app)

            # FIXME: check director service is in place and ready. Hand-shake??
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1728
            await start_registry_sync_task(app)

        if app.state.settings.CATALOG_TRACING:
            setup_tracing(app, app.state.settings.CATALOG_TRACING)

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
