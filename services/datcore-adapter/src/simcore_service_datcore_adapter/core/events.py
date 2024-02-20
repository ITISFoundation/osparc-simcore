import logging
from typing import Callable

from fastapi import FastAPI

from .._meta import PROJECT_NAME, __version__

logger = logging.getLogger(__name__)

#
# SEE https://patorjk.com/software/taag/#p=display&h=0&f=Graffiti&t=Datcore-Adapter
#
WELCOME_MSG = r"""

________             __                                               _____       .___                  __
\______ \  _____   _/  |_   ____    ____  _______   ____             /  _  \    __| _/_____   ______  _/  |_   ____  _______
 |    |  \ \__  \  \   __\_/ ___\  /  _ \ \_  __ \_/ __ \   ______  /  /_\  \  / __ | \__  \  \____ \ \   __\_/ __ \ \_  __ \
 |    `   \ / __ \_ |  |  \  \___ (  <_> ) |  | \/\  ___/  /_____/ /    |    \/ /_/ |  / __ \_|  |_> > |  |  \  ___/  |  | \/
/_______  /(____  / |__|   \___  > \____/  |__|    \___  >         \____|__  /\____ | (____  /|   __/  |__|   \___  > |__|
        \/      \/             \/                      \/                  \/      \/      \/ |__|                \/              {}
""".format(
    f"v{__version__}"
)


def on_startup() -> None:
    print(WELCOME_MSG, flush=True)


def on_shutdown() -> None:
    msg = PROJECT_NAME + f" v{__version__} SHUT DOWN"
    print(f"{msg:=^100}", flush=True)


def create_start_app_handler(_app: FastAPI) -> Callable:
    async def start_app() -> None:
        logger.info("Application started")

    return start_app


def create_stop_app_handler(_app: FastAPI) -> Callable:
    async def stop_app() -> None:
        logger.info("Application stopping")

    return stop_app
