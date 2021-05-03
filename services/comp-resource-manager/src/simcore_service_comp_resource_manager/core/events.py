import logging
from typing import Callable

from fastapi import FastAPI

from .._meta import __version__, project_name
from ..db.events import close_db_connection, connect_to_db

logger = logging.getLogger(__name__)

#
# https://patorjk.com/software/taag/#p=display&f=JS%20Stick%20Letters&t=comp-resource-manager%0A
#
WELCOME_MSG = r"""

  ,--,  .---.           ,---.           ,---.    ,---.     .---.  .---.  .-. .-.,---.   ,--,  ,---.                   .--.  .-. .-.  .--.    ,--,   ,---.  ,---.
.' .') / .-. ) |\    /| | .-.\          | .-.\   | .-'    ( .-._)/ .-. ) | | | || .-.\.' .')  | .-'         |\    /| / /\ \ |  \| | / /\ \ .' .'    | .-'  | .-.\
|  |(_)| | |(_)|(\  / | | |-' )____.___ | `-'/   | `-.   (_) \   | | |(_)| | | || `-'/|  |(_) | `-.____.___ |(\  / |/ /__\ \|   | |/ /__\ \|  |  __ | `-.  | `-'/
\  \   | | | | (_)\/  | | |--' `----==='|   (    | .-'   _  \ \  | | | | | | | ||   ( \  \    | .-'`----==='(_)\/  ||  __  || |\  ||  __  |\  \ ( _)| .-'  |   (
 \  `-.\ `-' / | \  / | | |             | |\ \   |  `--.( `-'  ) \ `-' / | `-')|| |\ \ \  `-. |  `--.       | \  / || |  |)|| | |)|| |  |)| \  `-) )|  `--.| |\ \
  \____\)---'  | |\/| | /(              |_| \)\  /( __.' `----'   )---'  `---(_)|_| \)\ \____\/( __.'       | |\/| ||_|  (_)/(  (_)|_|  (_) )\____/ /( __.'|_| \)\
       (_)     '-'  '-'(__)                 (__)(__)             (_)                (__)     (__)           '-'  '-'       (__)            (__)    (__)        (__)  {0}

""".format(
    f"v{__version__}"
)


def create_start_app_handler(app: FastAPI) -> Callable:
    async def on_startup() -> None:

        print(WELCOME_MSG, flush=True)

    return on_startup


def create_stop_app_handler(app: FastAPI) -> Callable:
    async def on_shutdown() -> None:
        logger.info("Application stopping")

        msg = project_name + f" v{__version__} SHUT DOWN"
        print(f"{msg:=^100}")

    return on_shutdown
