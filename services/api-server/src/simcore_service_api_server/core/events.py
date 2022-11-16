import logging
from typing import Callable

from fastapi import FastAPI

from .._meta import PROJECT_NAME, __version__
from ..db.events import close_db_connection, connect_to_db

logger = logging.getLogger(__name__)

#
# https://patorjk.com/software/taag/#p=display&f=JS%20Stick%20Letters&t=API-server%0A
#
WELCOME_MSG = r"""
      __        __   ___  __        ___  __
 /\  |__) | __ /__` |__  |__) \  / |__  |__)
/~~\ |    |    .__/ |___ |  \  \/  |___ |  \  {}

""".format(
    f"v{__version__}"
)


def create_start_app_handler(app: FastAPI) -> Callable:
    async def on_startup() -> None:
        logger.info("Application starting")
        if app.state.settings.API_SERVER_POSTGRES:
            # database
            await connect_to_db(app)
            assert app.state.engine  # nosec

        print(WELCOME_MSG, flush=True)

    return on_startup


def create_stop_app_handler(app: FastAPI) -> Callable:
    async def on_shutdown() -> None:
        logger.info("Application stopping")

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

        msg = PROJECT_NAME + f" v{__version__} SHUT DOWN"
        print(f"{msg:=^100}")

    return on_shutdown
